#!/usr/bin/env python
"""GPU 설정 및 성능 진단 스크립트

Ollama가 GPU를 제대로 사용하고 있는지 확인합니다.
사용법: python check_gpu.py
"""

import os
import subprocess
import sys
import platform

def print_section(title):
    """섹션 헤더 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def check_environment_variables():
    """환경변수 확인"""
    print_section("1. Ollama 환경변수 설정")
    
    env_vars = {
        'OLLAMA_NUM_GPU': '모든 레이어를 GPU에 로드 (-1 권장)',
        'OLLAMA_GPU_MEMORY': 'GPU 메모리 한계 (예: 4gi)',
        'OLLAMA_HOST': 'Ollama 서버 주소 (기본: localhost:11434)',
    }
    
    for var_name, description in env_vars.items():
        value = os.environ.get(var_name, '미설정')
        status = "✓" if value != '미설정' else "✗"
        print(f"{status} {var_name:20} = {value:30} ({description})")

def check_cuda():
    """CUDA 설치 확인 (NVIDIA GPU)"""
    print_section("2. CUDA 설치 확인 (NVIDIA GPU)")
    
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ NVIDIA GPU 감지됨!")
            print("\n GPU 정보:")
            # 첫 10줄만 출력
            for line in result.stdout.split('\n')[:10]:
                print(f"  {line}")
        else:
            print("✗ NVIDIA GPU를 찾을 수 없습니다.")
    except FileNotFoundError:
        print("✗ nvidia-smi를 찾을 수 없습니다. (NVIDIA Driver/CUDA 미설치)")
    except subprocess.TimeoutExpired:
        print("✗ nvidia-smi 실행 시간 초과")
    except Exception as e:
        print(f"✗ 오류: {e}")

def check_rocm():
    """ROCm 설치 확인 (AMD GPU)"""
    print_section("3. ROCm 설치 확인 (AMD GPU)")
    
    try:
        result = subprocess.run(['rocm-smi'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ AMD GPU 감지됨!")
            print("\n GPU 정보:")
            print(result.stdout[:500])
        else:
            print("✗ AMD GPU를 찾을 수 없습니다.")
    except FileNotFoundError:
        print("✗ rocm-smi를 찾을 수 없습니다. (ROCm 미설치)")
    except subprocess.TimeoutExpired:
        print("✗ rocm-smi 실행 시간 초과")
    except Exception as e:
        print(f"✗ 오류: {e}")

def check_ollama_status():
    """Ollama 서버 상태 확인"""
    print_section("4. Ollama 서버 상태")
    
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ Ollama 서버 정상 작동 중")
            print("\n 설치된 모델:")
            print(result.stdout)
        else:
            print("✗ Ollama 서버에 연결할 수 없습니다.")
            print("  해결방법: 'ollama serve' 명령으로 Ollama 서버를 시작하세요.")
    except FileNotFoundError:
        print("✗ ollama 명령어를 찾을 수 없습니다. (Ollama 미설치)")
    except subprocess.TimeoutExpired:
        print("✗ ollama list 실행 시간 초과")
    except Exception as e:
        print(f"✗ 오류: {e}")

def check_python_libraries():
    """Python 라이브러리 확인"""
    print_section("5. Python 라이브러리")
    
    required_libs = {
        'langchain_ollama': 'LangChain Ollama 통합',
        'langchain_core': 'LangChain 코어',
        'pandas': '데이터 처리',
        'sqlite3': 'SQLite (내장)',
    }
    
    for lib_name, description in required_libs.items():
        try:
            __import__(lib_name)
            print(f"✓ {lib_name:20} - {description}")
        except ImportError:
            print(f"✗ {lib_name:20} - {description} (미설치)")

def recommendation():
    """권장사항"""
    print_section("6. 권장 설정")
    
    print("""
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
""")

def main():
    """메인 진단 함수"""
    print("\n")
    print(" "*60)
    print("  Ollama GPU 설정 진단 도구")
    print(" "*60)
    
    system_info = platform.platform()
    print(f"\n시스템 정보: {system_info}")
    
    check_environment_variables()
    
    if platform.system() == "Windows" or platform.system() == "Linux":
        check_cuda()
        check_rocm()
    
    check_ollama_status()
    check_python_libraries()
    recommendation()
    
    print("\n" + "="*60)
    print("  진단 완료")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()

