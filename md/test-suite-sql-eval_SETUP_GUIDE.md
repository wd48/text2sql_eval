
***

## 통합 방법: 단계별 가이드

### 1단계 — 환경 설정 및 레포 클론

```bash
# test-suite-sql-eval을 프로젝트 하위에 통합
cd text2sql_eval
git clone https://github.com/taoyds/test-suite-sql-eval ./eval/test-suite-sql-eval

# 의존성 설치
pip install sqlparse nltk langchain-community langchain-core ollama
```

Spider 테스트 DB(Test Suite databases)는 별도로 다운로드 후 `eval/test-suite-sql-eval/database/`에 배치해야 합니다

***

### 2단계 — main.py에 결과 저장 로직 구현

현재 주석 처리된 루프를 채워서 `predict.txt` 형식으로 출력합니다.

```python
# main.py — 주석 해제 및 구현
import csv

def load_questions(path: str) -> list:
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))  # question, schema, db_id 컬럼 필요

def save_results(results: list, out_path: str):
    with open(out_path, 'w', encoding='utf-8') as f:
        for sql in results:
            f.write(sql + '\n')

def main():
    # ... (기존 argparse, runner factory 코드) ...

    questions = load_questions(args.questions_file)
    predicted_sqls = []
    for q in questions:
        sql = runner.generate_sql(q['question'], q['schema'])
        predicted_sqls.append(sql)

    save_results(predicted_sqls, "predict.txt")
    print(f"✅ predict.txt 저장 완료 ({len(predicted_sqls)}건)")
```
***

### 3단계 — gold.txt 포맷 준비

test-suite-sql-eval이 요구하는 `gold.txt` 형식은 `정답SQL\tdb_id` 입니다 .

```
# gold.txt 예시 (evaluation_examples/gold.txt 포맷 참고)
SELECT name FROM employees WHERE salary = MAX(salary)	company_db
SELECT COUNT(*) FROM orders WHERE status = 'delivered'	shop_db
```

CSV 질문 파일에 `gold_sql`과 `db_id` 컬럼을 포함시켜 gold.txt 생성 스크립트를 별도로 만드는 것을 권장합니다.

***

### 4단계 — eval/eval.py 구현 (통합 연결)

```python
# eval/eval.py — test-suite-sql-eval을 호출하는 래퍼
import subprocess
import sys
import os

def run_evaluation(
    gold_file: str,
    pred_file: str,
    db_dir: str,
    table_file: str,
    etype: str = "exec",
    plug_value: bool = True
):
    eval_script = os.path.join(
        os.path.dirname(__file__),
        "test-suite-sql-eval", "evaluation.py"
    )
    cmd = [
        sys.executable, eval_script,
        "--gold", gold_file,
        "--pred", pred_file,
        "--db",   db_dir,
        "--table", table_file,
        "--etype", etype,
        "--progress_bar_for_each_datapoint"
    ]
    if plug_value:
        cmd.append("--plug_value")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
    return result.stdout
```

***

### 5단계 — 전체 파이프라인 실행 흐름

```
# 1. SQL 생성
python main.py -m llama3-langchain -q ./data/questions.csv
# → predict.txt 생성

# 2. 평가 실행
python evaluation.py \
  --gold ./data/gold.txt \
  --pred ./predict.txt \
  --db   ./eval/test-suite-sql-eval/database \
  --table ./eval/test-suite-sql-eval/tables.json \
  --etype exec \
  --plug_value \
  --progress_bar_for_each_datapoint
```



***

## 최종 디렉토리 구조 (통합 후)

```
text2sql_eval/
├── main.py                          ← load_questions/save_results 구현
├── runners/
│   ├── langchain_runner.py          ← 4단계 파이프라인 (기존)
│   └── api_runner.py
├── prompts/
│   └── prompt_langchain.json
├── eval/
│   ├── eval.py                      ← test-suite 호출 래퍼 구현
│   └── test-suite-sql-eval/         ← 신규 클론
│       ├── evaluation.py            ← Spider/SParC/CoSQL 평가
│       ├── evaluate_classical.py    ← 고전 데이터셋 평가
│       ├── exec_eval.py
│       ├── database/                ← Test Suite DBs (별도 다운로드)
│       └── tables.json
└── data/
    ├── questions.csv                ← question, schema, db_id, gold_sql
    └── gold.txt                     ← 정답SQL\tdb_id
```

***

## 주의사항

- **`--plug_value` 플래그**: Ollama 로컬 LLM은 값(value) 예측이 불안정할 수 있어, 초기 테스트에서는 이 플래그를 켜두는 것이 권장됩니다
- **`database/` 폴더 크기**: Spider test suite DB가 수백 MB이므로 별도 다운로드 링크([Google Drive](https://drive.google.com/file/d/1mkCx2GOFIqNesD4y8TDAO1yX1QZORP5w/view?usp=sharing))에서 받아야 합니다
- **`keep_distinct` 생략**: 기존 Exact Set Match와 공정하게 비교하려면 `--keep_distinct`를 붙이지 않아야 합니다

