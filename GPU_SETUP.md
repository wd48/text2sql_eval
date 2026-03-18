# GPU 설정 가이드 (GPU Configuration Guide)

## 📋 목차
1. [현재 상태](#현재-상태)
2. [GPU 활성화 방법](#gpu-활성화-방법)
3. [성능 테스트](#성능-테스트)
4. [문제 해결](#문제-해결)

---

## 현재 상태

✅ **GPU 환경변수 설정 완료**
- `OLLAMA_NUM_GPU = -1`: 모든 레이어를 GPU에서 실행
- 환경: Windows 10, Ollama v0.18.1, gemma3n 7.5GB

❓ **CUDA/ROCm 상태**
- NVIDIA GPU: 설치 여부 확인 필요
- AMD GPU: ROCm 설치 확인 필요
- Ollama 자체 CUDA 번들 사용 가능

✅ **코드 수정 사항**
```
✓ langchain_runner.py: GPU 환경변수 자동 설정
✓ main.py: 시작 시 GPU 활성화
✓ check_gpu.py: GPU 진단 도구 추가
✓ test_gpu_performance.py: 성능 테스트 스크립트
```

---

## GPU 활성화 방법

### 방법 1: 자동 활성화 (권장)
프로젝트의 모든 Python 스크립트는 실행 시 자동으로 GPU를 활성화합니다.

```powershell
# 그냥 실행하면 됩니다
.\.venv\Scripts\python.exe .\main.py -m llama3-langchain -q questions.csv
```

**내부 메커니즘:**
```python
# langchain_runner.py, main.py 상단에 자동 설정됨
if not os.environ.get('OLLAMA_NUM_GPU'):
    os.environ['OLLAMA_NUM_GPU'] = '-1'
```

### 방법 2: 명시적 환경변수 설정

**현재 PowerShell 세션에만 적용:**
```powershell
$env:OLLAMA_NUM_GPU = "-1"
.\.venv\Scripts\python.exe .\main.py -m llama3-langchain -q questions.csv
```

**시스템 전체에 영구 설정 (관리자 권한 필요):**
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_GPU", "-1", "Machine")
# 설정 후 새로운 PowerShell/IDE 재시작
```

### 방법 3: CPU 강제 실행 (디버깅용)

```powershell
$env:OLLAMA_NUM_GPU = "0"  # GPU 사용 안 함 (CPU만 사용)
.\.venv\Scripts\python.exe .\main.py -m llama3-langchain -q questions.csv
```

---

## 성능 테스트

### 테스트 1: GPU 상태 진단

```powershell
Set-Location "E:\study\python\text2sql_eval"
.\.venv\Scripts\python.exe check_gpu.py
```

**출력 예시:**
```
✓ OLLAMA_NUM_GPU       = -1                    (모든 레이어를 GPU에 로드)
✓ Ollama 서버 정상 작동 중
✓ langchain_ollama     - LangChain Ollama 통합
```

### 테스트 2: GPU 성능 벤치마크

```powershell
$env:OLLAMA_NUM_GPU = "-1"
.\.venv\Scripts\python.exe test_gpu_performance.py
```

**예상 출력:**
```
[테스트 1/3]
질문: 직원의 이름을 찾아주세요
생성된 SQL: SELECT name FROM employees
실행 시간: 21.82초
```

### 테스트 3: 전체 파이프라인

```powershell
$env:OLLAMA_NUM_GPU = "-1"
.\.venv\Scripts\python.exe .\main.py -m llama3-langchain -q ".\참고자료\questions\questions_gen_sqlite.csv"
```

---

## 환경변수 설정값 설명

| 변수 | 값 | 설명 |
|------|---|------|
| `OLLAMA_NUM_GPU` | `-1` | 모든 레이어 GPU 로드 (권장) |
| | `0` | GPU 미사용, CPU만 실행 |
| | `N` | N개 레이어만 GPU에 로드 |
| `OLLAMA_GPU_MEMORY` | `4gi` | 최대 4GB GPU 메모리 사용 |
| `OLLAMA_HOST` | `localhost:11434` | Ollama 서버 주소 (기본값) |

**메모리 설정 예시:**
```powershell
# GPU 메모리를 4GB로 제한 (메모리 부족 시)
$env:OLLAMA_GPU_MEMORY = "4gi"
$env:OLLAMA_NUM_GPU = "-1"
```

---

## 성능 비교

### 속도 차이 (gemma3n 모델, 추정값)

| 설정 | 4단계 파이프라인 시간 | 특징 |
|------|-----------------|------|
| GPU (OLLAMA_NUM_GPU=-1) | ~20초 | ✅ 빠름, 메모리 많이 사용 |
| GPU (부분로드) | ~30-40초 | 절충형 |
| CPU (OLLAMA_NUM_GPU=0) | ~60-120초 | 느리지만 가능 |

### 실제 측정 결과

```
[테스트 1] 간단한 SELECT
GPU:  21.82초
CPU:  ~90초 (추정)

[테스트 2] 복잡한 GROUP BY
GPU:  ~25초
CPU:  ~100초 (추정)
```

---

## CUDA/ROCm 설치 (선택사항)

현재 Windows 환경에서는 설치되지 않아도 **Ollama가 자체 CUDA 번들**을 사용합니다.

### NVIDIA GPU용 CUDA 설치 (선택)

1. **NVIDIA Driver 확인**
   ```powershell
   nvidia-smi  # 또는 설치하기
   ```

2. **CUDA Toolkit 다운로드**
   https://developer.nvidia.com/cuda-downloads

3. **확인**
   ```powershell
   nvcc --version  # CUDA 설치 확인
   ```

### AMD GPU용 ROCm 설치 (선택)

1. **ROCm 다운로드**
   https://rocmdocs.amd.com/en/docs/deploy/windows/quick_start.html

2. **확인**
   ```powershell
   rocm-smi  # AMD GPU 정보 확인
   ```

---

## 문제 해결

### 문제 1: GPU 사용하지 않음

**증상:** `실행 시간: 120초+` (너무 느림)

**진단:**
```powershell
.\.venv\Scripts\python.exe check_gpu.py
```

**해결:**
```powershell
# 1. 환경변수 설정 확인
$env:OLLAMA_NUM_GPU  # "-1"이 보여야 함

# 2. 수동으로 설정
$env:OLLAMA_NUM_GPU = "-1"

# 3. Ollama 서버 재시작
# (다른 터미널에서) ollama serve
```

### 문제 2: Out of Memory (GPU 메모리 부족)

**증상:** 실행 중 "CUDA out of memory" 에러

**해결:**
```powershell
# 일부 레이어만 GPU 사용
$env:OLLAMA_NUM_GPU = "20"  # 20개 레이어만

# 또는 메모리 제한
$env:OLLAMA_GPU_MEMORY = "4gi"
```

### 문제 3: Ollama 서버 미실행

**증상:** "ConnectionError: failed to connect to Ollama"

**해결:**
```powershell
# 별도 터미널에서 Ollama 서버 시작
ollama serve

# 또는 백그라운드 실행
Start-Process ollama -ArgumentList "serve" -NoNewWindow
```

### 문제 4: Python 3.14 경고 (무시해도 됨)

```
UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14
```

**설명:** LangChain의 Python 3.14 호환성 경고입니다.
**영향:** 기능에 문제 없음
**해결:** Python 3.11/3.12로 변경 (선택사항)

---

## 빠른 참고

```powershell
# GPU 활성화 + 성능 테스트
$env:OLLAMA_NUM_GPU = "-1"
.\.venv\Scripts\python.exe test_gpu_performance.py

# GPU 상태 진단
.\.venv\Scripts\python.exe check_gpu.py

# 전체 파이프라인 실행
.\.venv\Scripts\python.exe .\main.py -m llama3-langchain -q ".\참고자료\questions\questions_gen_sqlite.csv"
```

---

**마지막 업데이트:** 2026-03-19

