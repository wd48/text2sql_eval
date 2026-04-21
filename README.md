# sql-eval 기반 Text-to-SQL 고도화 파이프라인 구축 (DIN-SQL & MMSQL 적용)


## 목차

- [1. 프로젝트 개요](#1-프로젝트-개요-overview)
- [2. 빠른 시작](#2-빠른-시작-quick-start)
- [2-1. 결과 JSON 디버깅 컬럼](#2-1-결과-json-디버깅-컬럼)
- [3. 핵심 설계 원칙](#3-핵심-설계-원칙-core-design-principles)
- [4. 파이프라인 구조적 흐름](#4-파이프라인-구조적-흐름-pipeline-architecture-flow)
- [5. 디렉토리 및 모듈 구조](#5-디렉토리-및-모듈-구조-directory--module-structure)
- [6. 구현된 기능 상세](#6-구현된-기능-상세-implemented-features-detaillink)
- [7. Spider 벤치마크 데이터셋](#7-spider-벤치마크-데이터셋-spider-benchmark-dataset)
- [8. 다음 단계](#8-다음-단계-next-steps)
- [9. Reference Links](#9-reference-links)
- [10. 최근 변경사항](#10-최근-변경사항-recent-changes)

### 📚 상세 문서 바로가기

- [PIPELINE_GUIDE.md](md/PIPELINE_GUIDE.md) - 파이프라인 완전 가이드
- [COMPLETION_REPORT.md](md/COMPLETION_REPORT.md) - 최종 완성 보고서
- [README_5_Details.md](md/README_5_Details.md) - 구현된 기능 상세 설명
- [GPU_SETUP.md](md/GPU_SETUP.md) - GPU 사용 설정 가이드
- [checkGPU.md](md/checkGPU.md) - GPU 상태 점검 방법
- [test-suite-sql-eval_SETUP_GUIDE.md](md/test-suite-sql-eval_SETUP_GUIDE.md) - 평가 엔진 설치 가이드

---

### 🚀 빠른 시작 (Quick Start - 3단계)

```powershell
# 1️⃣ Ollama 서버 시작 (별도 터미널)
ollama serve

# 2️⃣ 데이터셋 생성
python make_csv.py

# 3️⃣ SQL 생성 + 자동 평가 ⭐ (NEW: eval.py 통합!)
python main.py -m llama3-langchain -q questions.csv
```

**예상 결과:**
```
📈 최종 평가 결과:
   전체 질문: 20
   정답: 18
   정확도: 90.00% ⭐
```

---

## 1. 프로젝트 개요 (Overview)

본 프로젝트는 오픈소스 Text-to-SQL 평가 프레임워크인 `sql-eval`의 구조를 기반으로, 최신 연구인 **DIN-SQL**과 **MMSQL** 논문의 방법론을 결합하여 고도화된 쿼리 생성 시스템을 설계하는 것을 목표로 합니다.

복잡한 데이터베이스 환경과 Multi-turn 대화 상황에서 발생하는 Hallucination을 줄이고 쿼리의 정확도를 높이기 위해, 단순한 프롬프트 방식(Zero-shot/Few-shot)을 넘어선 **다단계 추론 파이프라인(Decomposition)** 을 구축합니다. 시스템 오케스트레이션을 위해 **LangChain**을 도입하며, 로컬 환경에서의 안전하고 유연한 추론을 위해 **Ollama**를 활용합니다.

### 핵심 기술 스택
- **LLM Framework:** LangChain LCEL (Expression Language) 기반 파이프라인 자동화
- **로컬 LLM:** Ollama (gemma3n, llama3 등 오픈소스 모델 지원)
- **평가 엔진:** SQLite 기반 실행 정확도 검증
- **벤치마크 데이터셋:** Spider (자동 SQL 평가 스탠다드)

## 🚀 빠른 시작 (Quick Start)

### 1단계: 가상환경 활성화 및 Ollama 서버 실행

```powershell
# 가상환경 활성화
Set-Location "E:\study\python\text2sql_eval"
.\.venv\Scripts\Activate.ps1

# (별도의 터미널에서) Ollama 서버 시작
ollama serve
```

### 2단계: GPU 설정 확인

```powershell
# GPU 설정 상태 진단
python check_gpu.py

# 환경변수 설정 (GPU 활성화)
$env:OLLAMA_NUM_GPU = "-1"
```

### 3단계: 모델 실행

```powershell
# 테스트 질문으로 SQL 생성 (gemma3n 모델)
python .\main.py -m llama3-langchain -q ".\참고자료\questions\questions_gen_sqlite.csv"

# 또는 직접 runner 테스트
python runners/langchain_runner.py
```

### 예상 출력

```
최종 생성된 SQL:
 SELECT name
FROM employees
WHERE department = '영업팀'
ORDER BY salary DESC
LIMIT 1;
```

### 2-1. 결과 JSON 디버깅 컬럼

`main.py` 실행 후 생성되는 `results.json`에는 최종 SQL뿐 아니라 중간 단계 디버깅 정보도 함께 저장됩니다.

| 컬럼 | 설명 |
|------|------|
| `classification_result` | Phase 1 분류 단계의 원본 응답 텍스트 |
| `classification_label` | 정규화된 분류 라벨 (`Answerable`, `Ambiguous`, `Unanswerable`, `Unknown`) |
| `linked_schema` | Phase 2에서 추출한 축소 스키마 |
| `draft_sql` | Phase 3에서 생성한 초안 SQL |
| `predicted_sql` | Phase 4 보정 후 최종 SQL |

또한 콘솔에는 `classification_label` 분포와 `Unanswerable` 비율이 통계로 출력되어 프롬프트/스키마 품질을 빠르게 진단할 수 있습니다.

---

## 2. 핵심 설계 원칙 (Core Design Principles)

이 시스템은 두 논문의 핵심 개념을 시스템 아키텍처로 승화시킵니다.

* **사전 필터링 (MMSQL 기반):** 모든 사용자 입력이 유효한 SQL로 변환될 수 있다는 가정을 버립니다. 쿼리 생성 전 단계에서 질문의 의도와 스키마의 한계를 분석하여 시스템의 신뢰성을 방어합니다.
* **작업 분할 및 컨텍스트 최적화 (DIN-SQL 기반):** 거대한 Database Schema 전체를 LLM에 한 번에 주입하지 않습니다. 문제를 잘게 쪼개어(Decomposition) 각 단계마다 LLM이 집중해야 할 컨텍스트(Context)의 크기를 최소화하고 추론의 질을 높입니다.
* **자가 검증 루프 (Self-Correction):** 단일 생성으로 작업을 끝내지 않고, 생성된 결과물과 스키마 구조를 다시 대조하는 검증 단계를 파이프라인 내부에 내장합니다.

### 구현 전략
- **온프레미스 LLM:** Ollama를 통해 로컬 GPU/CPU에서 오픈소스 LLM 실행 (데이터 유출 방지, 비용 최소화)
- **LangChain LCEL:** 함수형 파이프라인으로 각 단계 간 데이터 흐름을 선언적으로 정의하여 유지보수성과 확장성 확보
- **온디맨드 임포트:** 모델별 의존성을 지연 로딩하여 환경 점프 시 불필요한 경고/에러 방지

---

## 3. 파이프라인 구조적 흐름 (Pipeline Architecture Flow)

시스템은 LangChain의 Chain을 통해 다음 4개의 주요 노드(Node)를 순차적으로 통과하는 흐름으로 설계됩니다.

### **Phase 1. Question Classification (질문 분류 및 검증)**

* **Input:** 사용자 질문 (Multi-turn 대화 기록 포함), 전체 Database Schema
* **Process:** LLM이 현재 스키마로 질문에 답변할 수 있는지 평가합니다.
* **Output:** `Answerable`, `Ambiguous`(모호함), `Unanswerable`(답변 불가) 중 하나로 상태를 반환합니다.
* **Flow Control:** `Answerable`인 경우에만 다음 단계로 진입하며, 그 외의 경우 사용자에게 추가 컨텍스트를 요구하거나 에러 메시지를 반환하여 불필요한 연산을 차단합니다.
* **구현:** `langchain_runner.py`의 `phase_1_classification` 프롬프트 사용, 답변 불가 판정 시 파이프라인 즉시 종료

### **Phase 2. Schema Linking (스키마 링킹)**

* **Input:** 검증된 사용자 질문, 전체 Database Schema
* **Process:** 수십~수백 개의 테이블과 컬럼 중, 질문과 직접적으로 매핑되는 최소한의 Table, Column, Foreign Key 정보만을 추출합니다.
* **Output:** 질문에 최적화된 **축소된 스키마(Linked Schema)**
* **효과:** LLM의 컨텍스트 윈도우 부담을 줄이고 추론 정확도 향상

### **Phase 3. Draft Generation (초안 쿼리 생성)**

* **Input:** 사용자 질문, **축소된 스키마(Linked Schema)**
* **Process:** 최소한의 정보로 압축된 스키마 컨텍스트를 바탕으로 1차 SQL 쿼리문을 작성합니다.
* **Output:** Draft SQL (초안 쿼리)
* **특징:** Phase 2의 축소된 컨텍스트를 사용하므로 비교적 빠르고 정확한 생성 가능

### **Phase 4. Self-Correction (자가 교정 및 최종 산출)**

* **Input:** 사용자 질문, Draft SQL, 관련 스키마 정보
* **Process:** 초안 쿼리가 문법적으로 올바른지, 명시된 조건이 누락되지 않았는지, JOIN 조건(Foreign Key)이나 GROUP BY 절이 정확한지 LLM 스스로 다시 검토하고 수정합니다.
* **Output:** Final SQL (최종 쿼리, 여백/마크다운 제거 후처리 포함)
* **장점:** 모델의 자가 교정 능력을 활용하여 단순 생성 대비 높은 정확도 달성

### 파이프라인 실행 흐름도
```
User Question + DB Schema
         ↓
   [Phase 1: Classification]
         ↓
    Answerable? → No → Return Error Message & Stop
         ↓ Yes
   [Phase 2: Schema Linking]
         ↓
   [Phase 3: Draft Generation]
         ↓
   [Phase 4: Self-Correction]
         ↓
   Final SQL + Post-processing
```

---

## 4. 디렉토리 및 모듈 구조 (Directory & Module Structure)

기존 `sql-eval` 시스템의 확장성을 활용하여, 논문의 파이프라인을 독립적인 모듈로 플러그인(Plug-in)하는 구조를 취합니다.

```text
text2sql_eval/
├── main.py                     # CLI 진입점 (Runner Factory 패턴, 모델별 라우팅)
│
├── prompts/                    # 프롬프트 관리 계층 (Prompt Manager)
│   └── prompt_langchain.json   # 4단계 파이프라인용 세분화된 프롬프트 템플릿
│                               # - phase_1_classification: 질문 검증
│                               # - phase_2_schema_linking: 필요 테이블/컬럼 추출
│                               # - phase_3_draft_generation: 초안 SQL 생성
│                               # - phase_4_self_correction: 자가 교정 및 최종화
│
├── runners/                    # LLM 실행 계층 (Execution Runners)
│   ├── api_runner.py           # Base Runner (향후 OpenAI 등 추가 모델 확장용)
│   └── langchain_runner.py     # [핵심] LangChain + Ollama 기반 4단계 파이프라인 오케스트레이션
│                               # - LangChainOllamaRunner 클래스: Phase 1~4 순차 실행
│                               # - 프롬프트 로드 및 체인 구성
│                               # - 조기 종료 최적화 (Answerable 판정 후만 계속)
│                               # - SQL 후처리 (마크다운 제거)
│
├── utils/                      # 유틸리티 계층
│   └── llm.py                  # OllamaLLMManager 클래스
│                               # - Ollama LLM 공통 관리 및 체인 생성
│                               # - temperature=0.0으로 결정론적 생성 지원
│
├── eval/                       # 평가 및 검증 계층 (Evaluation)
│   └── eval.py                 # SQL 실행 정확도 검증
│                               # - evaluate_execution_accuracy(): 예측 SQL vs 정답 SQL
│                               # - run_evaluation_suite(): 대량 평가 및 통계
│                               # - SQLite 기반 실행 및 결과 셋 비교
│
├── 참고자료/                   # 참고 자료 폴더
│   ├── paper/                  # 벤치마크 논문
│   │   ├── 2023NeurIPS_DIN-SQL_Decomposed.pdf
│   │   └── Evaluating and Enhancing LLMs for Muti-turn Text-to-SQL...pdf
│   └── questions/              # 테스트용 질문 데이터셋 (로컬 환경, 용량 제약)
│       ├── questions_gen_sqlite.csv
│       ├── questions_gen_mysql.csv
│       └── questions_gen_postgres.csv
│
└── README.md                   # 이 파일
```

### 주요 클래스 및 메서드

#### `LangChainOllamaRunner` (runners/langchain_runner.py)
- **`__init__(model_name, prompt_file_path)`:** Ollama 모델 초기화, 프롬프트 로드
- **`generate_sql(question, schema)`:** 4단계 파이프라인 순차 실행, 최종 SQL 반환
- **`_load_prompts(filepath)`:** JSON 파일에서 프롬프트 템플릿 로드

#### `OllamaLLMManager` (utils/llm.py)
- **`__init__(model_name, temperature)`:** Ollama LLM 초기화
- **`get_chain(prompt_template_str)`:** 프롬프트 | LLM | 파서 체인 생성
- **`invoke(prompt_template_str, **kwargs)`:** 단발성 LLM 호출

#### `evaluate_execution_accuracy()` (eval/eval.py)
- **입력:** DB 경로, 예측 SQL, 정답 SQL
- **출력:** bool (두 결과 셋이 동일하면 True)
- **오류 처리:** SQL 문법 오류, 존재하지 않는 테이블/컬럼 → False 반환

---

## 5. [구현된 기능 상세 Implemented Features Detail(link)](md/README_5_Details.md)

---

## 6. Spider 벤치마크 데이터셋 (Spider Benchmark Dataset)

### 6.1 Spider 소개

**Spider (Structured Query Language to Python Interpreter Exquisite Retrieval)**는 Text-to-SQL 태스크의 **표준 벤치마크**입니다.

- **논문:** Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task (Yale & Salesforce Research, 2018)
- **데이터 규모:** 10,181개의 (질문, SQL) 쌍 / 200개의 다양한 데이터베이스
- **목표:** 일반적이고 도메인 무관한(Domain-agnostic) SQL 생성 능력 평가

### 6.2 Spider 데이터셋 구조

```
spider/
├── database/                          # 200개 데이터베이스 SQLite 파일 (약 2.5GB)
│   ├── academic/academic.sqlite
│   ├── adult/adult.sqlite
│   ├── basketball_1/basketball_1.sqlite
│   └── ... (196개 더)
│
├── train_spider.json                  # 학습용 (7,493개 질문)
├── dev.json                           # 검증용 (1,034개 질문)
├── test_spider.json                   # 테스트용 (2,026개 질문) - 정답 미공개
└── tables.json                        # 전체 데이터베이스 스키마 정보
```

### 6.3 Spider JSON 포맷

**train_spider.json 예시:**
```json
[
  {
    "question": "Find the names of students who have taken both organic chemistry and inorganic chemistry courses.",
    "question_toks": ["Find", "the", "names", "..."],
    "db_id": "academic",
    "sql": {
      "select": [1],
      "from": {"table_units": [[0, "student"]], "conds": []},
      ...
    },
    "query": "SELECT t1.name FROM student AS t1 WHERE EXISTS (SELECT * FROM takes AS t2, course AS t3 WHERE t2.course_id = t3.course_id AND t3.name = 'organic chemistry' AND t2.student_id = t1.student_id) AND EXISTS (...)"
  },
  ...
]
```

**tables.json 예시 (스키마 정보):**
```json
{
  "db_id": "academic",
  "table_names": ["student", "course", "takes", ...],
  "table_names_original": ["student", "course", "takes", ...],
  "column_names": [[0, "student_id"], [0, "name"], [1, "course_id"], ...],
  "column_names_original": [[0, "student_id"], [0, "name"], ...],
  "column_types": ["number", "text", ...],
  "primary_keys": [1, 4, ...],
  "foreign_keys": [[2, 5], [3, 6], ...],
  "db_path": "database/academic/academic.sqlite"
}
```

### 6.4 로컬 환경에서의 Spider 활용 (용량 제약)

본 프로젝트에서는 **로컬 환경의 저장 공간 제약**으로 인해 Spider 전체 데이터셋을 포함하지 않습니다. 대신 다음과 같이 활용합니다:

#### 방식 1: Spider dataset 전체 다운로드
```bash
# Spider 공식 홈페이지에서 'spider dataset' 다운로드
# https://yale-lily.github.io/spider

# 해당 페이지 내 'Getting Started'
# https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view?usp=sharing
```

#### 방식 2: 필요한 DB만 선택적 다운로드
```bash
# Spider 공식 저장소에서 특정 DB만 다운로드
# https://github.com/taoyds/spider

# 예: academic DB만 다운로드
wget https://download.microsoft.com/download/.../academic.zip
unzip academic.zip -d spider/database/
```

#### 방식 3: 참고자료/questions 사용 (현재 방식)
본 프로젝트의 `참고자료/questions/` 디렉토리에는 수동으로 구성한 테스트 데이터셋이 있습니다:
- `questions_gen_sqlite.csv`: SQLite용 질문 샘플 (간단한 도메인)
- `questions_gen_mysql.csv`: MySQL용 질문 샘플
- `questions_gen_postgres.csv`: PostgreSQL용 질문 샘플

**포맷:**
```csv
question,schema,gold_sql
"직원 이름을 찾아주세요","Table: employees, Columns: [emp_id, name, department]","SELECT name FROM employees"
```

#### 방식 3: Spider 미니 벤치마크 구축 (권장)
Spider의 20~50개 데이터베이스를 선택하여 로컬에 저장:
```python
# 예: 작은 DB 5개만 선택
selected_dbs = ["academic", "atis", "bookkeeping_1", "cardinality", "device_1"]

# 각 DB에서 10~20개 질문만 샘플링하여 로컬 JSON 생성
import json
subset = []
for item in spider_train:
    if item["db_id"] in selected_dbs:
        subset.append(item)
        
with open("spider_mini.json", "w") as f:
    json.dump(subset, f)
```

### 6.5 Spider 정확도 평가 방식

#### 1. **Exact Match Accuracy (정확한 일치)**
- 생성된 SQL과 정답 SQL이 **정확하게 일치**하는 비율
- 문법/순서 차이 → 오답 판정

#### 2. **Execution Accuracy (실행 정확도)** ⭐ 본 프로젝트 방식
- 두 쿼리를 실제 DB에서 실행
- **결과 셋이 동일**하면 정답 판정
- 문법은 다르지만 결과가 같으면 정답

```python
# 본 프로젝트의 eval.py에서 사용하는 방식
def evaluate_execution_accuracy(db_path, predicted_sql, gold_sql):
    # DB에서 두 쿼리 실행
    gold_result = execute_query(db_path, gold_sql)
    pred_result = execute_query(db_path, predicted_sql)
    
    # 결과 셋 비교 (순서 무관)
    return set(gold_result) == set(pred_result)
```

### 6.6 Spider 벤치마크에서의 모델 성능 기준

| 모델 | Exec Accuracy | 출시연도 | 특징 |
|------|---------------|---------|------|
| GPT-3.5 | ~60% | 2022 | Few-shot 한계 |
| Text-davinci-003 | ~72% | 2022 | 프롬프트 민감성 높음 |
| GPT-4 | ~79% | 2023 | 복잡한 조인 약함 |
| DIN-SQL | ~85% | 2023 | 분해식 파이프라인 + 스키마 링크 |
| Claude-3 Opus | ~87% | 2024 | 최고 성능 (폐쇄형) |
| 오픈소스 (Llama2-13B) | ~45% | 2023 | 로컬 실행 가능 |

**본 프로젝트의 목표:**
- `gemma3n` 기본선: 30~40% (빠른 프로토타입)
- `llama3` 최적화: 50~60% (로컬 모델 한계)
- OpenAI API 통합 시: 75~80% (클라우드 고성능)

### 6.7 Spider 데이터셋 활용 가이드

#### Step 1: Spider 공식 데이터 다운로드
```bash
git clone https://github.com/taoyds/spider.git
cd spider
# database/, tables.json, train_spider.json 등 확인
```

#### Step 2: 로컬 프로젝트에 포함 (선택사항)
```bash
cp -r spider/database ./참고자료/spider_database  # 용량이 크므로 선택적
cp spider/tables.json ./참고자료/
cp spider/train_spider.json ./참고자료/
```

#### Step 3: 데이터 로드 및 평가
```python
import json
import pandas as pd

# Spider 데이터 로드
with open("참고자료/train_spider.json") as f:
    spider_train = json.load(f)

# 사용할 질문 샘플 추출
sample_questions = [
    {
        "question": item["question"],
        "db_id": item["db_id"],
        "gold_sql": item["query"]
    }
    for item in spider_train[:100]  # 100개만 샘플
]

# main.py와 연동하여 평가
for q in sample_questions:
    predicted_sql = runner.generate_sql(q["question"], get_schema(q["db_id"]))
    accuracy = evaluate_execution_accuracy(
        f"spider/database/{q['db_id']}/{q['db_id']}.sqlite",
        predicted_sql,
        q["gold_sql"]
    )
```

---

## 7. 다음 단계 (Next Steps)

1. **프롬프트 엔지니어링:** `prompts/prompt_langchain.json` 내의 각 단계별(Phase 1~4) 세부 프롬프트 템플릿 설계 및 최적화
2. **Runner 구현 확장:** `runners/langchain_runner.py` 내에 LangChain LCEL 구조를 활용한 모듈 간 데이터 전달 로직 및 코드 구현
3. **모델 연동 및 테스트:** Ollama를 통한 로컬 오픈소스 LLM 연동 및 Spider 벤치마크 데이터셋을 활용한 성능 측정
4. **SQLite DB 통합:** 로컬 샘플 데이터베이스(Chinook, Northwind 등) 구축 및 실제 평가 파이프라인 완성

---

## 8. Reference Links

[sql-eval github link](https://github.com/defog-ai/sql-eval)   
[Spider: A Large-Scale Human-Labeled Dataset](https://github.com/taoyds/spider)   
[DIN-SQL 논문](참고자료/paper/2023NeurIPS_DIN-SQL_Decomposed.pdf)  
[MMSQL 논문](참고자료/paper/Evaluating%20and%20Enhancing%20LLMs%20for%20Muti-turn%20Text-to-SQL%20with%20Multiple%20Question%20Types.pdf)  

---

## 📝 최근 변경사항 (Recent Changes)

### ✅ 파이프라인 완성: eval.py 통합 + CSV 포맷 통일 완료 (2026.03.31)
**주요 완성 사항:**

| 항목 | 상태 | 설명 |
|------|------|------|
| **eval.py 통합** | ✅ 완료 | main.py에서 SQL 생성 후 자동 평가 (동적 DB 경로) |
| **CSV 포맷 통일** | ✅ 완료 | make_csv.py ↔ main.py 완벽 호환 (db_name, db_type 추가) |
| **실제 스키마 추출** | ✅ 완료 | SQLite PRAGMA table_info로 실제 DB 스키마 자동 추출 |
| **통합 검증** | ✅ 완료 | test_pipeline.py 모든 검증 통과 |

### 🧪 test-suite-sql-eval 통합 요약 (2026.04.02)
**주요 연동 사항:**

| 항목 | 상태 | 설명 |
|------|------|------|
| **test-suite-sql-eval 배치** | ✅ 완료 | `eval/test-suite-sql-eval` 경로에 평가 엔진 통합 |
| **평가 입력 포맷** | ✅ 정리 | `gold.txt`는 `정답SQL\tdb_id`, `predict.txt`는 예측 SQL 한 줄 형식 |
| **평가 방식** | ✅ 지원 | `evaluation.py` 기반 `exec` 중심 평가, 필요 시 `match`/`all` 확장 가능 |
| **DB 리소스** | ✅ 분리 | Spider Test Suite DB는 용량상 로컬 별도 다운로드 후 `database/`에 배치 |
| **상세 가이드** | ✅ 문서화 | 설치/실행 절차는 `md/test-suite-sql-eval_SETUP_GUIDE.md` 참고 |
