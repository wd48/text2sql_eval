# sql-eval 기반 Text-to-SQL 고도화 파이프라인 구축 (DIN-SQL & MMSQL 적용)

## 1. 프로젝트 개요 (Overview)

본 프로젝트는 오픈소스 Text-to-SQL 평가 프레임워크인 `sql-eval`의 구조를 기반으로, 최신 연구인 **DIN-SQL**과 **MMSQL** 논문의 방법론을 결합하여 고도화된 쿼리 생성 시스템을 설계하는 것을 목표로 합니다.

복잡한 데이터베이스 환경과 Multi-turn 대화 상황에서 발생하는 Hallucination을 줄이고 쿼리의 정확도를 높이기 위해, 단순한 프롬프트 방식(Zero-shot/Few-shot)을 넘어선 **다단계 추론 파이프라인(Decomposition)** 을 구축합니다. 시스템 오케스트레이션을 위해 **LangChain**을 도입하며, 로컬 환경에서의 안전하고 유연한 추론을 위해 **Ollama**를 활용합니다.

---

## 2. 핵심 설계 원칙 (Core Design Principles)

이 시스템은 두 논문의 핵심 개념을 시스템 아키텍처로 승화시킵니다.

* **사전 필터링 (MMSQL 기반):** 모든 사용자 입력이 유효한 SQL로 변환될 수 있다는 가정을 버립니다. 쿼리 생성 전 단계에서 질문의 의도와 스키마의 한계를 분석하여 시스템의 신뢰성을 방어합니다.
* **작업 분할 및 컨텍스트 최적화 (DIN-SQL 기반):** 거대한 Database Schema 전체를 LLM에 한 번에 주입하지 않습니다. 문제를 잘게 쪼개어(Decomposition) 각 단계마다 LLM이 집중해야 할 컨텍스트(Context)의 크기를 최소화하고 추론의 질을 높입니다.
* **자가 검증 루프 (Self-Correction):** 단일 생성으로 작업을 끝내지 않고, 생성된 결과물과 스키마 구조를 다시 대조하는 검증 단계를 파이프라인 내부에 내장합니다.

---

## 3. 파이프라인 구조적 흐름 (Pipeline Architecture Flow)

시스템은 LangChain의 Chain을 통해 다음 4개의 주요 노드(Node)를 순차적으로 통과하는 흐름으로 설계됩니다.

### **Phase 1. Question Classification (질문 분류 및 검증)**

* **Input:** 사용자 질문 (Multi-turn 대화 기록 포함), 전체 Database Schema
* **Process:** LLM이 현재 스키마로 질문에 답변할 수 있는지 평가합니다.
* **Output:** `Answerable`, `Ambiguous`(모호함), `Unanswerable`(답변 불가) 중 하나로 상태를 반환합니다.
* **Flow Control:** `Answerable`인 경우에만 다음 단계로 진입하며, 그 외의 경우 사용자에게 추가 컨텍스트를 요구하거나 에러 메시지를 반환하여 불필요한 연산을 차단합니다.

### **Phase 2. Schema Linking (스키마 링킹)**

* **Input:** 검증된 사용자 질문, 전체 Database Schema
* **Process:** 수십~수백 개의 테이블과 컬럼 중, 질문과 직접적으로 매핑되는 최소한의 Table, Column, Foreign Key 정보만을 추출합니다.
* **Output:** 질문에 최적화된 **축소된 스키마(Linked Schema)**

### **Phase 3. Draft Generation (초안 쿼리 생성)**

* **Input:** 사용자 질문, **축소된 스키마(Linked Schema)**
* **Process:** 최소한의 정보로 압축된 스키마 컨텍스트를 바탕으로 1차 SQL 쿼리문을 작성합니다.
* **Output:** Draft SQL (초안 쿼리)

### **Phase 4. Self-Correction (자가 교정 및 최종 산출)**

* **Input:** 사용자 질문, Draft SQL, 관련 스키마 정보
* **Process:** 초안 쿼리가 문법적으로 올바른지, 명시된 조건이 누락되지 않았는지, JOIN 조건(Foreign Key)이나 GROUP BY 절이 정확한지 LLM 스스로 다시 검토하고 수정합니다.
* **Output:** Final SQL (최종 쿼리)

---

## 4. 디렉토리 및 모듈 구조 (Directory & Module Structure)

기존 `sql-eval` 시스템의 확장성을 활용하여, 논문의 파이프라인을 독립적인 모듈로 플러그인(Plug-in)하는 구조를 취합니다.

```text
sql-eval/
├── main.py                     # 전체 평가 프레임워크의 진입점 (새로운 파이프라인 라우팅 추가)
│
├── prompts/                    # 프롬프트 관리 계층 (Prompt Manager)
│   ├── prompt_openai.json      # (기존) 단일 프롬프트 템플릿
│   └── prompt_langchain.json   # [신규] 4단계 파이프라인(분류->링킹->생성->교정)을 위한 세분화된 템플릿
│
├── runners/                    # LLM 실행 계층 (Execution Runners)
│   ├── api_runner.py           # (기존) Base Runner
│   └── langchain_runner.py     # [신규] LangChain + Ollama 기반의 오케스트레이션 Runner
│                               # (Phase 1 ~ 4의 파이프라인 흐름 제어 담당)
│
└── eval/                       # 평가 및 검증 계층 (Evaluation)
    └── eval.py                 # 최종 생성된 SQL의 Execution Accuracy 검증 (기존 로직 활용)

```

## 5. 다음 단계 (Next Steps)

1. **프롬프트 엔지니어링:** `prompts/prompt_langchain.json` 내의 각 단계별(Phase 1~4) 세부 프롬프트 템플릿 설계 및 최적화
2. **Runner 구현:** `runners/langchain_runner.py` 내에 LangChain LCEL 구조를 활용한 모듈 간 데이터 전달 로직 및 코드 구현
3. **모델 연동 및 테스트:** Ollama를 통한 로컬 오픈소스 LLM 연동 및 기존 `sql-eval` 벤치마크 데이터셋을 활용한 성능 측정

## 6. reference link

[sql-eval github link](https://github.com/defog-ai/sql-eval)   
[DIN-SQL 논문](참고자료/paper/2023NeurIPS_DIN-SQL_Decomposed.pdf)  
[MMSQL 논문](참고자료/paper/2023NeurIPS_DIN-SQL_Decomposed.pdf)  