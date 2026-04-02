
### 5.1 Command-Line Interface (CLI) - `main.py`

```bash
python main.py -m <MODEL> -q <QUESTIONS_FILE>
```

**주요 인자:**
- `-m/--model`: 사용할 모델 선택
  - `llama3-langchain`: Ollama llama3 모델 사용 (프로덕션용)
  - `gpt-4`: OpenAI GPT-4 (향후 구현)
- `-q/--questions_file`: 입력 질문 CSV 파일 경로

**구현 특징:**
- **Factory 패턴:** 모델별 Runner를 동적으로 선택하여 확장성 극대화
- **온디맨드 임포트:** 선택된 모델의 의존성만 로드 (Python 3.14 경고 최소화)

### 5.2 4단계 파이프라인 (Phase 1~4) - `langchain_runner.py`

#### Phase 1: Question Classification
```json
{
  "phase_1_classification": "You are a database expert. Classify if the following question can be answered using the provided database schema.\nSchema: {schema}\nQuestion: {question}\nRespond strictly with one of these words: [Answerable, Ambiguous, Unanswerable]."
}
```
- **목적:** 불가능한 질문의 조기 감지로 불필요한 연산 차단
- **최적화:** "Answerable"이 아니면 파이프라인 즉시 종료

#### Phase 2: Schema Linking
```json
{
  "phase_2_schema_linking": "Given the following database schema, extract ONLY the tables and columns necessary to answer the user's question.\nSchema: {schema}\nQuestion: {question}\nOutput the linked schema in JSON format."
}
```
- **목적:** 거대한 스키마를 질문에 맞는 부분만 축소
- **효과:** 컨텍스트 윈도우 절감, 추론 정확도 향상

#### Phase 3: Draft Generation
```json
{
  "phase_3_draft_generation": "Write a valid SQLite query to answer the question based on the provided linked schema.\nLinked Schema: {linked_schema}\nQuestion: {question}\nOutput ONLY the SQL query."
}
```
- **입력:** 축소된 스키마 사용으로 빠른 생성
- **출력:** 1차 SQL 쿼리 (여러 문제 가능성 있음)

#### Phase 4: Self-Correction
```json
{
  "phase_4_self_correction": "Review the following SQLite query for the given question.\n- Ensure all tables and columns exist in the schema.\n- Check if JOIN conditions (Foreign Keys) are correct.\n- Ensure GROUP BY matches the SELECT clause.\nQuestion: {question}\nDraft SQL: {draft_sql}\nSchema: {schema}\nOutput the corrected SQL query ONLY."
}
```
- **목적:** 초안의 문법/논리 오류 교정
- **효과:** 단순 생성보다 높은 정확도

### 5.3 SQL 실행 정확도 평가 - `eval/eval.py`

#### `evaluate_execution_accuracy(db_path, predicted_sql, gold_sql)`
```python
def evaluate_execution_accuracy(db_path: str, predicted_sql: str, gold_sql: str) -> bool:
    """
    예측된 SQL과 정답 SQL을 실제 DB에서 실행하고, 결과 셋이 동일한지 검증합니다.
    """
```

**특징:**
- **실제 DB 실행:** SQLite 연결 후 두 쿼리 모두 실행
- **결과 셋 비교:** Set으로 변환하여 순서 무관 비교
- **오류 처리:** SQL 문법 오류, 존재하지 않는 테이블/컬럼 → False 반환

#### `run_evaluation_suite(results_df, db_path)`
```python
def run_evaluation_suite(results_df: pd.DataFrame, db_path: str) -> dict:
    """
    전체 결과 데이터프레임을 순회하며 정확도를 계산합니다.
    """
```

**입력 요구사항:**
- `results_df`: 'gold_sql'과 'predicted_sql' 컬럼 포함
- `db_path`: SQLite DB 경로

**출력:**
- 정확도, 오류율, 통계 정보를 포함한 dict

### 5.4 LLM 관리 유틸리티 - `utils/llm.py`

#### `OllamaLLMManager` 클래스
```python
class OllamaLLMManager:
    def __init__(self, model_name: str = "llama3", temperature: float = 0.0):
        # temperature=0.0: SQL 생성 같은 결정론적 작업에 최적화
    
    def get_chain(self, prompt_template_str: str):
        # 프롬프트 | LLM | 파서 체인 생성
    
    def invoke(self, prompt_template_str: str, **kwargs) -> str:
        # 단발성 LLM 호출 (프롬프트 + 변수 → 결과)
```

**사용 예:**
```python
from utils.llm import OllamaLLMManager

manager = OllamaLLMManager(model_name="gemma3n")
result = manager.invoke("Classify: {text}", text="좋은 리뷰입니다")
```

### 5.5 Ollama 모델 지원

**현재 테스트된 모델:**
- `gemma3n` (7.5GB, 경량, 빠름, 한국어 미흡)
- `llama3` (미설치, 약 4.5GB)

**설치 명령:**
```powershell
ollama pull gemma3n    # 설치됨
ollama pull llama3     # 선택사항
ollama list            # 설치된 모델 확인
```

**모델 성능 비교:**
| 모델 | 크기 | 속도 | 정확도 | 한국어 | 추천 용도 |
|------|------|------|-------|--------|----------|
| gemma3n | 7.5GB | 빠름 | 중간 | 약함 | 빠른 프로토타입 |
| llama3 | 4.5GB | 중간 | 높음 | 중간 | 정확도 우선 |

### 5.6 GPU 활성화 설정 (CUDA/ROCm)

본 시스템은 **GPU 가속**을 기본으로 지원합니다. Ollama가 설치되어 있고 CUDA/ROCm이 설치된 환경에서는 자동으로 GPU를 감지하여 사용합니다.

#### GPU 활성화 확인

**현재 상태 확인:**
```powershell
# Ollama가 GPU를 사용하고 있는지 확인
$env:OLLAMA_NUM_GPU
$env:OLLAMA_GPU_MEMORY

# 또는 ollama 실행 시 로그 확인
ollama run gemma3n "test"
```

#### GPU 환경변수 설정 (명시적 활성화)

**Windows 환경 (PowerShell에서 영구 설정):**
```powershell
# 현재 세션에만 적용
$env:OLLAMA_NUM_GPU = "-1"

# 또는 시스템 전체에 적용 (관리자 권한)
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_GPU", "-1", "Machine")
```

**환경변수 설명:**
- `OLLAMA_NUM_GPU=-1`: 모든 모델 레이어를 GPU 메모리에 로드 (권장, 최고 성능)
- `OLLAMA_NUM_GPU=0`: GPU 사용 안 함 (CPU 전용)
- `OLLAMA_NUM_GPU=N`: N개의 레이어만 GPU에 로드 (메모리 부족 시)
- `OLLAMA_GPU_MEMORY=Xgi`: GPU 메모리 한계 설정 (예: 4gi = 4GB)

#### GPU 확인 및 벤치마크

**현재 GPU 사용 상태 확인:**
```python
import os
import subprocess

# 환경변수 확인
print(f"OLLAMA_NUM_GPU: {os.environ.get('OLLAMA_NUM_GPU', 'not set')}")
print(f"OLLAMA_GPU_MEMORY: {os.environ.get('OLLAMA_GPU_MEMORY', 'not set')}")

# Ollama 프로세스 정보 (Windows)
result = subprocess.run(
    ["tasklist", "/v"],
    capture_output=True,
    text=True
)
for line in result.stdout.split('\n'):
    if 'ollama' in line.lower():
        print(f"Ollama Process: {line}")
```

**성능 비교 (추정값, 환경에 따라 다름):**

| 설정 | gemma3n 속도 | llama3 속도 | GPU 메모리 |
|:------|:-------------|:-----------|:----------|
| GPU (OLLAMA_NUM_GPU=-1) | ~1초/토큰 | ~0.5초/토큰 | ~6GB+ |
| GPU (부분로드) | ~2초/토큰 | ~1초/토큰 | ~3~4GB |
| CPU (GPU 미사용) | ~5~10초/토큰 | ~10~20초/토큰 | ~500MB |

#### CUDA/ROCm 설치 여부 확인

**CUDA 설치 확인 (NVIDIA GPU):**
```powershell
# NVIDIA GPU 정보
nvidia-smi

# CUDA 버전 확인
nvcc --version
```

**ROCm 설치 확인 (AMD GPU):**
```powershell
# AMD GPU 정보
rocm-smi

# ROCm 버전 확인
hipcc --version
```

#### GPU 진단 도구 사용 (신규)

본 프로젝트에 포함된 **`check_gpu.py`** 스크립트로 GPU 설정 상태를 즉시 진단할 수 있습니다.

```powershell
Set-Location "E:\study\python\text2sql_eval"
.\.venv\Scripts\python.exe check_gpu.py
```

**출력 예시:**
```
============================================================
  1. Ollama 환경변수 설정
============================================================
✓ OLLAMA_NUM_GPU       = -1                    (모든 레이어를 GPU에 로드)
✗ OLLAMA_GPU_MEMORY    = 미설정                 (GPU 메모리 한계)

============================================================
  2. CUDA 설치 확인 (NVIDIA GPU)
============================================================
✗ nvidia-smi를 찾을 수 없습니다. (CUDA 미설치)

============================================================
  4. Ollama 서버 상태
============================================================
✓ Ollama 서버 정상 작동 중
```

**진단 항목:**
- ✓ Ollama 환경변수 설정 상태
- ✓ CUDA (NVIDIA GPU) 설치 여부
- ✓ ROCm (AMD GPU) 설치 여부
- ✓ Ollama 서버 정상 작동 여부
- ✓ 필요한 Python 라이브러리 설치 여부