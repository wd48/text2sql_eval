# LangChain + Ollama pipeline runner
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class LangChainOllamaRunner:
    def __init__(self, model_name="llama3", temperature=0.0):
        # 1. Ollama LLM 초기화 (로컬에서 Ollama 서버가 실행 중이어야 함)
        self.llm = ChatOllama(model=model_name, temperature=temperature)
        self.output_parser = StrOutputParser()

        # 2. 단계별 Prompt Templates 정의 (DIN-SQL 및 MMSQL 방법론 적용)
        self.class_prompt = ChatPromptTemplate.from_template(
            "주어진 Schema를 바탕으로 다음 질문에 답할 수 있는지 분류해.\n"
            "분류 기준: [Answerable, Ambiguous, Unanswerable]\n"
            "Schema: {schema}\n"
            "Question: {question}\n"
            "Classification:"
        )

        self.link_prompt = ChatPromptTemplate.from_template(
            "주어진 질문에 답하기 위해 필요한 Table과 Column을 Schema에서 찾아 나열해.\n"
            "Schema: {schema}\n"
            "Question: {question}\n"
            "Linked Schema:"
        )

        self.gen_prompt = ChatPromptTemplate.from_template(
            "다음 추출된 스키마 정보를 바탕으로 질문에 대한 SQLite SQL 쿼리를 작성해.\n"
            "Linked Schema: {linked_schema}\n"
            "Question: {question}\n"
            "SQL Query:"
        )

        self.correct_prompt = ChatPromptTemplate.from_template(
            "주어진 질문에 대해 작성된 SQLite SQL 쿼리를 검토하고 수정해.\n"
            "- 명시적으로 언급된 값을 사용했는지 확인\n"
            "- Foreign Key를 사용한 JOIN 조건이 맞는지 확인\n"
            "문제가 있다면 수정하고, 없다면 쿼리를 그대로 반환해.\n\n"
            "Question: {question}\n"
            "SQLite SQL Query: {draft_sql}\n"
            "Fixed SQL Query:"
        )

    def generate_sql(self, question: str, schema_info: str) -> str:
        """
        LangChain의 Chain을 활용한 단계별 추론(Decomposition) 파이프라인
        """
        # Step 1: Question Classification Chain (MMSQL)
        class_chain = self.class_prompt | self.llm | self.output_parser
        classification = class_chain.invoke({"schema": schema_info, "question": question})

        if "Unanswerable" in classification or "Ambiguous" in classification:
            return "ERROR: 질문이 모호하거나 답변할 수 없습니다."

        # Step 2: Schema Linking Chain (DIN-SQL)
        link_chain = self.link_prompt | self.llm | self.output_parser
        linked_schema = link_chain.invoke({"schema": schema_info, "question": question})

        # Step 3: Draft Query Generation Chain (DIN-SQL)
        gen_chain = self.gen_prompt | self.llm | self.output_parser
        draft_sql = gen_chain.invoke({"linked_schema": linked_schema, "question": question})

        # Step 4: Self-Correction Chain (DIN-SQL)
        # 생성된 초안을 다시 LLM에 넣어 검증
        correct_chain = self.correct_prompt | self.llm | self.output_parser
        final_sql = correct_chain.invoke({"draft_sql": draft_sql, "question": question})

        # 불필요한 마크다운 태그(예: ```sql ... ```) 제거 로직 추가 가능
        final_sql = final_sql.replace("```sql", "").replace("```", "").strip()

        return final_sql


# 실행 예시 (로컬에 Ollama가 설치되어 있고, llama3 모델이 pull 되어 있어야 함)
if __name__ == "__main__":
    runner = LangChainOllamaRunner(model_name="llama3")

    sample_schema = "Table: employees, Columns: [emp_id, name, department, salary]"
    sample_question = "영업팀에서 급여가 가장 높은 직원의 이름은 무엇인가요?"

    result_sql = runner.generate_sql(sample_question, sample_schema)
    print("최종 생성된 SQL:\n", result_sql)