# 📋 Text-to-SQL 평가 파이프라인 완전 가이드

## 🎯 전체 구조 개요

이 프로젝트는 **자연어 질문을 SQL로 변환**하고, **생성된 SQL의 정확도를 자동으로 평가**하는 End-to-End 파이프라인입니다.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: 데이터셋 준비                                              │
│  make_csv.py → questions.csv (Spider dev.json으로부터)           │
└────────────────┬──────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 2: SQL 생성                                                   │
│  main.py -m llama3-langchain -q questions.csv                      │
│  ├─ Phase 1: 질문 검증 (Answerable?)                             │
│  ├─ Phase 2: 스키마 링킹 (필요한 테이블만 추출)                 │
│  ├─ Phase 3: 초안 SQL 생성                                      │
│  └─ Phase 4: 자기 교정 (오류 수정)                              │
└────────────────┬──────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 3: SQL 평가                                                   │
│  eval.py → 실제 DB에서 실행하여 결과 비교                        │
│  ├─ 예측 SQL 실행                                              │
│  ├─ 정답 SQL 실행                                              │
│  └─ 결과 셋 비교 (정확도 계산)                                │
└────────────────┬──────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  결과 저장                                                           │
│  results.json (생성된 SQL + 평가 결과)                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Spider 데이터셋 구조

Spider는 **손으로 만든 Text-to-SQL 벤치마크**입니다.

```
spider/
├── dev.json              ← 개발용 질문 데이터 (1034개 쌍)
├── dev_gold.sql         ← 개발용 정답 SQL
├── tables.json          ← 스키마 정의 (테이블, 컬럼, 타입)
│
├── database/
│   ├── academic/
│   │   ├── academic.sqlite    ← 실제 DB 파일
│   │   └── academic.sql       ← 스키마 정의
│   ├── concert_singer/
│   │   ├── concert_singer.sqlite
│   │   └── concert_singer.sql
│   ├── ... (167개 데이터베이스)
│   └── zoo/
│
├── test.json            ← 테스트 세트
├── test_gold.sql
└── test_tables.json
```

**주요 특징:**
- 총 **11,840개 질문-SQL 쌍** (train/dev/test 분할)
- **167개의 다양한 데이터베이스** (학사관리, 항공사, 음악, 금융 등)
- 단순 SELECT부터 복잡한 JOIN, 서브쿼리까지 포함
- 자동 평가 가능 (쿼리 실행 결과로 검증)

---

## 🔧 파일별 역할 설명

### 1️⃣ **make_csv.py** - 데이터셋 변환

**목적:** Spider의 `dev.json`으로부터 `questions.csv` 생성

**입력:**
```
spider/dev.json
{
  "db_id": "concert_singer",
  "question": "어떤 콘서트가 가장 많은 티켓을 팔았나?",
  "query": "SELECT c.name FROM concerts c ORDER BY c.num_tickets DESC LIMIT 1"
}
```

**출력 (questions.csv):**
```csv
question,schema,gold_sql,db_name,db_type
"어떤 콘서트가 가장 많은 티켓을 팔았나?","Table: concerts, Columns: [id(INTEGER), name(TEXT), num_tickets(INTEGER)]","SELECT c.name ...",concert_singer,sqlite
```

**핵심 기능:**
- ✅ 실제 DB에서 스키마 추출 (PRAGMA table_info)
- ✅ 컬럼명 + 데이터타입 자동 수집
- ✅ `db_name` 컬럼 추가 (평가 시 DB 파일 경로 결정에 사용)
- ✅ 에러 처리 (DB 파일 없음 등)

**사용법:**
```powershell
python make_csv.py
```

**출력 예시:**
```
✓ questions.csv 생성 완료!
  처리됨: 20개
  건너뜀: 0개

💡 다음 명령으로 실행하세요:
   python main.py -m llama3-langchain -q questions.csv
```

---

### 2️⃣ **main.py** - 메인 파이프라인

**목적:** CSV 질문들을 LLM으로 SQL 생성 → 자동 평가

**입력:**
- `-m/--model`: 사용할 모델 (예: `llama3-langchain`)
- `-q/--questions_file`: CSV 파일 경로
- `-o/--output`: 결과 저장 경로 (선택, 기본값: `results.json`)
- `--no-eval`: 평가 단계 스킵 (선택)

**3가지 주요 기능:**

#### (1) load_questions() - CSV 파싱
```python
# 입력: questions.csv
# 출력: 파이썬 딕셔너리 리스트
[
  {
    "question": "...",
    "schema": "Table: ... Columns: [...]",
    "db_name": "concert_singer",
    "db_type": "sqlite",
    "gold_sql": "SELECT ..."
  }
]
```

**CSV 포맷 요구사항:**
```
question | schema | gold_sql | db_name | db_type (마지막 2개는 선택)
```

#### (2) SQL 생성 단계
```
[1/20] 어떤 콘서트가 가장 많은 티켓을 팔았나?
  → 생성된 SQL: SELECT c.name FROM concerts c ORDER BY...

[2/20] ...
```

LangChain의 4단계 파이프라인 사용:
- **Phase 1:** 질문 검증 (Answerable?)
- **Phase 2:** 스키마 링킹 (필요한 테이블만 추출)
- **Phase 3:** 초안 SQL 생성
- **Phase 4:** 자기 교정

#### (3) 평가 단계 (eval.py 통합)
```
📊 평가 단계 시작...

  [1] ✓ 어떤 콘서트가 가장 많은 티켓을 팔았나?...
  [2] ✗ 가수 중에서... (오류: table not found)
  [3] ⚠️  ... (DB 파일 없음)

============================================================
📈 최종 평가 결과:
   전체 질문: 20
   정답: 15
   정확도: 75.00%
============================================================
```

**평가 로직:**

```python
# eval.py의 evaluate_execution_accuracy() 호출
db_file = "../spider/database/concert_singer/concert_singer.sqlite"

# 정답 SQL 실행
gold_result = execute(db_file, gold_sql)

# 예측 SQL 실행  
predicted_result = execute(db_file, predicted_sql)

# 결과 비교 (순서 무관)
is_correct = set(gold_result) == set(predicted_result)
```

**사용법:**
```powershell
# 기본 실행
python main.py -m llama3-langchain -q questions.csv

# 평가 없이 SQL 생성만
python main.py -m llama3-langchain -q questions.csv --no-eval

# 커스텀 출력 경로
python main.py -m llama3-langchain -q questions.csv -o my_results.json
```

---

### 3️⃣ **eval.py** - 평가 엔진

**목적:** 생성된 SQL과 정답 SQL을 실제 DB에서 실행하여 정확도 평가

**2가지 함수:**

#### evaluate_execution_accuracy()
```python
def evaluate_execution_accuracy(
    db_path: str,           # "spider/database/concert_singer/concert_singer.sqlite"
    predicted_sql: str,     # LLM이 생성한 SQL
    gold_sql: str          # 정답 SQL
) -> bool:                  # 정확도 평가 결과 (True/False)
```

**로직:**
```python
conn = sqlite3.connect(db_path)

# 1. 정답 SQL 실행
gold_result = conn.execute(gold_sql).fetchall()

# 2. 예측 SQL 실행
predicted_result = conn.execute(predicted_sql).fetchall()

# 3. 결과 셋 비교 (Set으로 변환하여 순서 무관)
return set(gold_result) == set(predicted_result)
```

**에러 처리:**
- SQL 문법 오류 → False
- 존재하지 않는 테이블/컬럼 → False
- 기타 런타임 오류 → False

#### run_evaluation_suite()
```python
def run_evaluation_suite(
    results_df: pd.DataFrame,  # 'gold_sql', 'predicted_sql' 컬럼 필요
    db_path: str              # 데이터베이스 경로
) -> dict:                    # 통계 (정확도, 정답수 등)
```

**반환값:**
```python
{
  "total_queries": 20,
  "correct_queries": 15,
  "execution_accuracy": "75.00%"
}
```

---

### 4️⃣ **runners/langchain_runner.py** - LLM 파이프라인

**목적:** LangChain + Ollama를 이용한 4단계 SQL 생성

**클래스: LangChainOllamaRunner**

```python
runner = LangChainOllamaRunner(model_name="gemma3n:latest")
sql = runner.generate_sql(
    question="어떤 콘서트가 가장 많은 티켓을 팔았나?",
    schema="Table: concerts, Columns: [id, name, num_tickets]"
)
```

**4단계 파이프라인:**

| Phase | 입력 | 처리 | 출력 |
|-------|------|------|------|
| 1. 질문 분류 | 질문 + 전체 스키마 | LLM이 답변 가능 여부 판단 | Answerable/Unanswerable |
| 2. 스키마 링킹 | 질문 + 전체 스키마 | 질문과 관련된 테이블만 추출 | 축소된 스키마 |
| 3. 초안 생성 | 질문 + 축소 스키마 | SQL 쿼리 작성 | Draft SQL |
| 4. 자기 교정 | 질문 + 초안 + 전체 스키마 | 초안의 오류 수정 | Final SQL |

**GPU 설정:**
```python
# 자동 설정됨 (main.py의 맨 위에서)
os.environ['OLLAMA_NUM_GPU'] = '-1'  # 모든 레이어를 GPU에 로드
```

---

## 🎬 End-to-End 실행 흐름

### 1. 가상환경 활성화 & Ollama 서버 실행

```powershell
# PowerShell에서
.\.venv\Scripts\Activate.ps1

# 별도 터미널에서 Ollama 서버 시작
ollama serve
```

### 2. 데이터셋 준비

```powershell
# Spider의 dev.json으로부터 questions.csv 생성
python make_csv.py
```

**생성되는 파일:**
```
questions.csv
question,schema,gold_sql,db_name,db_type
"어떤 콘서트가 가장 많은 티켓을 팔았나?","Table: concerts, Columns: [...]","SELECT ...",concert_singer,sqlite
```

### 3. SQL 생성 & 평가

```powershell
python main.py -m llama3-langchain -q questions.csv
```

**예상 결과:**
```
🚀 모델 초기화: LangChain + Ollama (GPU 모드)

📂 질문 파일 로드: questions.csv
   → 20개 질문 로드됨

🔄 SQL 생성 단계 시작...

[1/20] 어떤 콘서트가 가장 많은 티켓을 팔았나?
  → 생성된 SQL: SELECT c.name FROM concerts c ORDER BY c.num_tickets DESC LIMIT 1...

[2/20] ...

📊 평가 단계 시작...

  [1] ✓ 어떤 콘서트가 가장 많은 티켓을 팔았나?...
  [2] ✗ ...

============================================================
📈 최종 평가 결과:
   전체 질문: 20
   정답: 15
   정확도: 75.00%
============================================================

✓ 결과 저장 완료 → results.json

✅ 작업 완료!
```

### 4. 결과 분석

```json
// results.json
[
  {
    "question": "어떤 콘서트가 가장 많은 티켓을 팔았나?",
    "schema": "Table: concerts, Columns: [...]",
    "db_name": "concert_singer",
    "predicted_sql": "SELECT c.name FROM concerts c ORDER BY c.num_tickets DESC LIMIT 1",
    "gold_sql": "SELECT c.name FROM concerts c ORDER BY c.num_tickets DESC LIMIT 1",
    "db_type": "sqlite",
    "is_correct": true
  },
  ...
]
```

---

## ⚙️ 컬럼 포맷 통일 정리

### **CSV 컬럼 명세**

| 컬럼명 | 필수 | 설명 |
|--------|------|------|
| `question` | ✅ | 자연어 질문 |
| `schema` | ✅ | DB 스키마 (테이블, 컬럼 정보) |
| `gold_sql` | ✅ | 정답 SQL |
| `db_name` | ⭕ | 데이터베이스 이름 (평가 시 DB 파일 경로 결정) |
| `db_type` | ⭕ | DB 타입 (기본값: sqlite) |

**주의:**
- `make_csv.py`의 출력과 `main.py`의 `load_questions()`가 이제 **일치**합니다
- 이전의 `query` 컬럼 → `gold_sql`로 통일
- `db_name` 컬럼은 평가 단계에서 **동적으로 DB 파일 경로**를 결정하는데 필수

---

## 🔍 문제 해결

### Q1. "DB 파일을 찾을 수 없습니다"
```
  [1] ⚠️  ... (DB 파일 없음)
```

**해결:**
1. `db_name` 컬럼이 정확한지 확인
2. `spider/database/{db_name}/{db_name}.sqlite` 파일이 존재하는지 확인
3. make_csv.py 재실행

### Q2. "Ollama 모델을 찾을 수 없습니다"
```
❌ 오류: Ollama 모델을 찾을 수 없습니다
```

**해결:**
```powershell
# Ollama 설치 (Windows: https://ollama.ai)
ollama pull gemma3n:latest
```

### Q3. SQL 실행 오류 (테이블 또는 컬럼 없음)
```
  [2] ✗ ... (오류: table not found)
```

**해결:**
- 스키마에 명시된 테이블명이 정확한지 확인
- `gold_sql`도 같은 오류가 나는지 검사 (정답 SQL이 오류면 데이터 문제)

---

## 📈 다음 단계

1. **모델 성능 비교**
   - 여러 LLM (`llama3`, `mistral` 등)으로 정확도 비교
   - Few-shot 프롬프트 최적화

2. **데이터셋 확대**
   - `train_spider.json` 활용 (5000+ 질문)
   - 정확도 통계 수집

3. **평가 지표 확대**
   - Execution Accuracy만이 아닌 다른 지표 추가
   - Error Analysis (어떤 유형의 질문에서 실패하는지)

4. **프롬프트 최적화**
   - `prompts/prompt_langchain.json` 수정
   - 특정 SQL 패턴에 대한 Few-shot 예제 추가

---

**💡 핵심 정리:**

✅ **make_csv.py** → `questions.csv` (db_name 포함)  
✅ **main.py** → CSV 읽기 → LLM으로 SQL 생성 → eval.py로 평가  
✅ **eval.py** → 실제 DB에서 실행 결과 비교 (Execution Accuracy)  
✅ **결과** → `results.json` (생성된 SQL + 평가 결과)

