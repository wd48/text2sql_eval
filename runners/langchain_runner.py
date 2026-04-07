# LangChain + Ollama pipeline runner
import json
import os

from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# GPU 설정: Ollama가 GPU를 사용하도록 환경변수 설정
# OLLAMA_NUM_GPU=-1: 모든 모델 레이어를 GPU에 로드
# CUDA/ROCm이 설치되어 있으면 자동으로 사용됩니다
if not os.environ.get('OLLAMA_NUM_GPU'):
    os.environ['OLLAMA_NUM_GPU'] = '-1'  # 모든 레이어를 GPU 메모리에 로드

""" LangChain LCEL 기반 4단계 파이프라인 핵심 로직
- Ollama LLM을 활용하여 질문 분류, 스키마 링크, 초안 생성, 자기 교정 단계로 SQL 생성
- 각 단계별로 명확한 프롬프트와 출력 파싱을 적용하여 모델의 추론을 체계적으로 유도
- 불필요한 LLM 호출을 방지하기 위해 질문 검증 단계에서 답변 불가 상태를 조기에 감지하여 파이프라인을 종료하는 최적화 적용
"""
class LangChainOllamaRunner:
    def __init__(self, model_name="gemma3n", prompt_file_path="prompts/prompt_langchain.json"):
        # 로컬 환경의 Ollama LLM 초기화
        # - temperature=0.1: 명확한 추론을 위해 낮게 설정 (결정론적 SQL 생성)
        # - GPU 사용: OLLAMA_NUM_GPU=-1로 설정되어 모든 레이어가 GPU에서 실행됨
        #   (CUDA/ROCm이 설치되어 있으면 자동으로 사용, 없으면 CPU로 fallback)
        self.llm = ChatOllama(model=model_name, temperature=0.1)
        self.output_parser = StrOutputParser()
        self.prompts = self._load_prompts(prompt_file_path)

    def _load_prompts(self, filepath):
        """JSON 파일에서 4단계 파이프라인용 프롬프트를 로드합니다."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 2026-04-07 옵션 추가
    # return_metadata=True 옵션이 활성화된 경우, 각 단계의 중간 결과와 분류 라벨을 포함한 상세 정보를 반환합니다.
    # classification_result, classification_label
    # linked_schema, draft_sql, predicted_sql
    def _normalize_classification(self, classification_result: str) -> str:
        """모델 응답에서 분류 라벨만 안정적으로 추출합니다."""
        text = (classification_result or "").strip()
        for label in ("Answerable", "Ambiguous", "Unanswerable"):
            if label.lower() in text.lower():
                return label
        first_token = text.split()[0] if text else ""
        return first_token.strip(",.:;()[]{}") or "Unknown"

    def generate_sql(self, question: str, schema: str, return_metadata: bool = False):
        """4 Phase 파이프라인을 순차적으로 실행하여 최종 SQL을 생성합니다."""

        # Phase 1: Question Classification (질문 검증)
        prompt_p1 = PromptTemplate.from_template(self.prompts["phase_1_classification"])
        chain_1 = prompt_p1 | self.llm | self.output_parser
        classification_result = chain_1.invoke({"question": question, "schema": schema}).strip()
        classification_label = self._normalize_classification(classification_result)

        # 분류 결과는 참고용으로만 사용하고, 답변 불가/모호 판정이어도
        # SQL 생성 파이프라인은 계속 진행한다.
        # 이렇게 해야 "시스템 알림" 문자열이 결과로 반환되는 것을 방지할 수 있다.

        # Phase 2: Schema Linking (필요한 Table/Column 추출)
        prompt_p2 = PromptTemplate.from_template(self.prompts["phase_2_schema_linking"])
        chain_2 = prompt_p2 | self.llm | self.output_parser
        linked_schema = chain_2.invoke({"question": question, "schema": schema})

        # Phase 3: Draft Generation (초안 생성)
        prompt_p3 = PromptTemplate.from_template(self.prompts["phase_3_draft_generation"])
        chain_3 = prompt_p3 | self.llm | self.output_parser
        draft_sql = chain_3.invoke({"question": question, "linked_schema": linked_schema})

        # Phase 4: Self-Correction (오류 교정 및 최종 출력)
        prompt_p4 = PromptTemplate.from_template(self.prompts["phase_4_self_correction"])
        chain_4 = prompt_p4 | self.llm | self.output_parser
        final_sql = chain_4.invoke({
            "question": question,
            "draft_sql": draft_sql,
            "schema": schema
        })

        # 쿼리 외의 불필요한 텍스트 제거 (후처리)
        final_sql = final_sql.replace("```sql", "").replace("```", "").strip()
        if return_metadata:
            return {
                "question": question,
                "schema": schema,
                "classification_result": classification_result,
                "classification_label": classification_label,
                "linked_schema": linked_schema,
                "draft_sql": draft_sql,
                "predicted_sql": final_sql,
            }
        return final_sql


# 실행 예시 (로컬에 Ollama가 설치되어 있고, 모델이 pull 되어 있어야 함)
if __name__ == "__main__":
    runner = LangChainOllamaRunner(model_name="gemma3n")

    sample_schema = "Table: employees, Columns: [emp_id, name, department, salary]"
    sample_question = "영업팀에서 급여가 가장 높은 직원의 이름은 무엇인가요?"

    result_sql = runner.generate_sql(sample_question, sample_schema)
    print("최종 생성된 SQL:\n", result_sql)