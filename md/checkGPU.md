  .\.venv\Scripts\python.exe .\main.py -m llama3-langchain -q questions.csv


                                                            
  Ollama GPU 설정 진단 도구
                                                            

시스템 정보: Windows-10-10.0.19045-SP0

============================================================
  1. Ollama 환경변수 설정
============================================================
✓ OLLAMA_NUM_GPU       = -1                             (모든 레이어를 GPU에 로드 (-1 권장))
✗ OLLAMA_GPU_MEMORY    = 미설정                            (GPU 메모리 한계 (예: 4gi))
✗ OLLAMA_HOST          = 미설정                            (Ollama 서버 주소 (기본: localhost:11434))

============================================================
  2. CUDA 설치 확인 (NVIDIA GPU)
============================================================
✗ nvidia-smi를 찾을 수 없습니다. (NVIDIA Driver/CUDA 미설치)

============================================================
  3. ROCm 설치 확인 (AMD GPU)
============================================================
✗ rocm-smi를 찾을 수 없습니다. (ROCm 미설치)

============================================================
  4. Ollama 서버 상태
============================================================
✓ Ollama 서버 정상 작동 중

 설치된 모델:
NAME              ID              SIZE      MODIFIED     
gemma3n:latest    15cb39fd9394    7.5 GB    6 months ago    


============================================================
  5. Python 라이브러리
============================================================
E:\study\python\text2sql_eval\.venv\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
  from pydantic.v1.fields import FieldInfo as FieldInfoV1
✓ langchain_ollama     - LangChain Ollama 통합
✓ langchain_core       - LangChain 코어
✓ pandas               - 데이터 처리
✓ sqlite3              - SQLite (내장)

============================================================
  6. 권장 설정
============================================================

GPU 성능을 최대한 활용하려면:

1. CUDA/ROCm 설치 확인
   - NVIDIA GPU: https://developer.nvidia.com/cuda-downloads
   - AMD GPU: https://rocmdocs.amd.com/

2. Ollama 서버 실행
   $ ollama serve
   
3. GPU 환경변수 설정 (PowerShell)
   $env:OLLAMA_NUM_GPU = "-1"
   
4. 프로젝트 실행
   .\.venv\Scripts\python.exe .\main.py -m llama3-langchain -q questions.csv

5. 성능 모니터링
   - NVIDIA: nvidia-smi --loop 1
   - AMD: rocm-smi --watch
