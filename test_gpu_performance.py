#!/usr/bin/env python
"""
GPU 가속 활성화 테스트 스크립트

간단한 SQL 생성 작업으로 GPU 가속 성능을 테스트합니다.
"""

import os
import time

# GPU 활성화 환경변수
if not os.environ.get('OLLAMA_NUM_GPU'):
    os.environ['OLLAMA_NUM_GPU'] = '-1'

from runners.langchain_runner import LangChainOllamaRunner

def test_gpu_performance():
    """GPU 가속 성능 테스트"""
    
    runner = LangChainOllamaRunner(model_name="gemma3n")
    
    test_cases = [
        {
            "question": "직원의 이름을 찾아주세요",
            "schema": "Table: employees, Columns: [emp_id, name, department, salary]"
        },
        {
            "question": "부서별 평균 급여를 계산해주세요",
            "schema": "Table: employees, Columns: [emp_id, name, department, salary]"
        },
        {
            "question": "급여가 50000 이상인 직원의 이름과 부서를 찾아주세요",
            "schema": "Table: employees, Columns: [emp_id, name, department, salary]"
        },
    ]
    
    print("\n" + "="*70)
    print("  GPU 가속 성능 테스트")
    print("="*70)
    print(f"OLLAMA_NUM_GPU: {os.environ.get('OLLAMA_NUM_GPU', 'not set')}")
    print("="*70 + "\n")
    
    for i, test in enumerate(test_cases, 1):
        print(f"[테스트 {i}/{len(test_cases)}]")
        print(f"질문: {test['question']}")
        print(f"스키마: {test['schema']}\n")
        
        start_time = time.time()
        result = runner.generate_sql(test["question"], test["schema"])
        elapsed = time.time() - start_time
        
        print(f"생성된 SQL:")
        print(f"  {result}")
        print(f"실행 시간: {elapsed:.2f}초\n")
    
    print("="*70)
    print("  테스트 완료")
    print("="*70)

if __name__ == "__main__":
    test_gpu_performance()

