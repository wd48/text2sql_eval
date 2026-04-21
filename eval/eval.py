from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

"""평가 유틸리티 모듈

- `evaluate_execution_accuracy`: 단일 SQLite DB에서 gold/pred 실행 결과를 비교하는 가벼운 평가
- `build_testsuite_eval_inputs`: `results.json` 스타일 결과를 test-suite 입력 파일로 변환
- `run_testsuite_eval`: 공식 `eval/test-suite-sql-eval/evaluation.py`를 서브프로세스로 실행
"""
# 2026-04-21: test-suite-eval 관련 함수 추가
def sanitize_sql(text: str) -> str:
    """코드펜스/언어태그/접두 노이즈를 제거하고 1줄 SQL로 정규화합니다."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^\s*`{1,3}\s*[a-zA-Z0-9_-]*\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?\s*`{1,3}\s*$", "", cleaned)
    cleaned = re.sub(r"^(sqlite|sql|ite)\b\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

# 2026-04-21: classification label 정규화 함수 추가 (오탈자 포함)
def normalize_classification_label(text: str) -> str:
    """classification_result 오탈자(예: Unaanswerable)를 포함해 라벨을 정규화합니다."""
    lowered = (text or "").strip().lower()
    if "unanswerable" in lowered or "unaanswerable" in lowered or "unaswerable" in lowered:
        return "Unanswerable"
    if "ambiguous" in lowered:
        return "Ambiguous"
    if "answerable" in lowered:
        return "Answerable"
    return "Unknown"

#
def evaluate_execution_accuracy(db_path: str, predicted_sql: str, gold_sql: str) -> bool:
    """단일 DB에서 실행 결과 셋이 같은지 검증합니다."""
    if not db_path or not Path(db_path).exists():
        return False

    predicted_sql = sanitize_sql(predicted_sql)
    gold_sql = sanitize_sql(gold_sql)
    if not predicted_sql or not gold_sql:
        return False

    try:
        conn = sqlite3.connect(db_path)
        # 타임아웃 방지 및 안전한 조회를 위해 읽기 전용 모드나 시간 제한을 거는 것이 좋습니다.
        cursor = conn.cursor()

        # 정답 SQL 실행
        cursor.execute(gold_sql)
        gold_result = cursor.fetchall()

        # 예측 SQL 실행
        cursor.execute(predicted_sql)
        predicted_result = cursor.fetchall()

        conn.close()

        # 결과 셋 비교 (레코드의 순서가 다를 수 있으므로 Set으로 변환하여 비교)
        return set(gold_result) == set(predicted_result)

    except sqlite3.Error as e:
        # 쿼리 문법 오류, 존재하지 않는 테이블/컬럼 참조 등의 에러 발생 시 False 처리
        # 디버깅을 위해 로그를 남겨두는 것이 좋습니다.
        print(f"[Eval Error] {e} | SQL: {predicted_sql}")
        return False
    except Exception as e:
        print(f"[Unexpected Eval Error] {e} | SQL: {predicted_sql}")
        return False


def run_evaluation_suite(results_df: pd.DataFrame, db_path: str) -> dict:
    """
    전체 결과 데이터프레임을 순회하며 정확도를 계산합니다.
    (results_df는 'gold_sql'과 'predicted_sql' 컬럼을 가지고 있어야 함)
    """
    total = len(results_df)
    correct = 0

    for _, row in results_df.iterrows():
        if evaluate_execution_accuracy(db_path, row["predicted_sql"], row["gold_sql"]):
            correct += 1

    accuracy = (correct / total) * 100 if total > 0 else 0.0
    return {
        "total_queries": total,
        "correct_queries": correct,
        "execution_accuracy": f"{accuracy:.2f}%",
    }
# 2026-04-21: test-suite-eval 입력 파일 생성 함수 추가
def build_testsuite_eval_inputs(
    results: list[dict[str, Any]],
    out_dir: str | Path,
    db_root: str | Path,
    gold_name: str = "testsuite_gold.txt",
    pred_name: str = "testsuite_pred.txt",
) -> dict[str, Any]:
    """test-suite-eval용 gold/pred 파일을 생성합니다.

    - gold 라인 형식: `gold_sql\tdb_id`
    - pred 라인 형식: `predicted_sql`
    - `db_id`가 test-suite DB 폴더에 없는 경우는 함께 건너뜁니다.
    """
    out_dir = Path(out_dir)
    db_root = Path(db_root)
    out_gold = out_dir / gold_name
    out_pred = out_dir / pred_name
    # available_db : 사용 가능한 DB list 미리 호출
    available_db = {p.name for p in db_root.iterdir() if p.is_dir()} if db_root.exists() else set()

    pairs: list[tuple[str, str]] = []
    skipped_no_db = 0
    skipped_empty = 0

    # results는 dict의 리스트로, 각 dict는 gold_sql, predicted_sql, db_name 등의 키를 가짐
    for row in results:

        # db_name이 row에 없거나, test-suite DB 폴더에 없는 경우는 skip
        db_id = (row.get("db_name") or "").strip()
        if not db_id or db_id not in available_db:
            skipped_no_db += 1
            continue

        # gold_sql과 predicted_sql이 모두 존재하는 경우에만 추가, 없으면 skip
        gold_sql = sanitize_sql(row.get("gold_sql") or "")
        pred_sql = sanitize_sql(row.get("predicted_sql") or "")
        if not gold_sql or not pred_sql:
            skipped_empty += 1
            continue

        # gold 라인 형식: `gold_sql\tdb_id`,
        # pred 라인 형식: `predicted_sql`
        pairs.append((f"{gold_sql}\t{db_id}", pred_sql))

    out_dir.mkdir(parents=True, exist_ok=True)
    # gold/pred 파일을 생성할 때, 각 라인 끝에 \n을 명시적으로 추가하여 줄바꿈이 일관되도록 합니다.
    with out_gold.open("w", encoding="utf-8", newline="\n") as fg, out_pred.open("w", encoding="utf-8", newline="\n") as fp:
        for gold_line, pred_line in pairs:
            fg.write(gold_line + "\n")
            fp.write(pred_line + "\n")

    return {
        "gold_path": out_gold,
        "pred_path": out_pred,
        "line_count": len(pairs),
        "skipped_no_db": skipped_no_db,
        "skipped_empty": skipped_empty,
    }

# 2026-04-21: test-suite-eval 출력에서 정확도 추출 함수 추가
def _parse_testsuite_accuracy(stdout: str) -> float | None:
    """공식 test-suite 출력에서 overall execution accuracy를 추출합니다."""
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("execution"):
            parts = stripped.split()
            try:
                return float(parts[-1])
            except (ValueError, IndexError):
                return None
    return None

# 2026-04-21: test-suite-eval 실행 함수 추가
def run_testsuite_eval(
    gold_path: str | Path,
    pred_path: str | Path,
    db_root: str | Path,
    table_path: str | Path | None = None,
    etype: str = "exec",
    plug_value: bool = True,
    keep_distinct: bool = False,
    progress_bar_for_each_datapoint: bool = False,
) -> dict[str, Any]:
    """공식 `evaluation.py`를 실행해 test-suite 평가를 수행합니다."""
    gold_path = Path(gold_path)
    pred_path = Path(pred_path)
    db_root = Path(db_root)
    evaluation_py = db_root.parent / "evaluation.py"

    if not evaluation_py.exists():
        raise FileNotFoundError(f"evaluation.py를 찾을 수 없습니다: {evaluation_py}")

    # 테스트 스위트 평가 스크립트는 커맨드라인 인자로 gold/pred 파일 경로, DB 루트, 테이블 정보 파일 경로 등을 받습니다.
    cmd = [
        sys.executable,
        str(evaluation_py),
        "--gold",
        str(gold_path),
        "--pred",
        str(pred_path),
        "--db",
        str(db_root),
        "--etype",
        etype,
    ]
    if table_path is not None:
        cmd.extend(["--table", str(table_path)])
    if plug_value:
        cmd.append("--plug_value")
    if keep_distinct:
        cmd.append("--keep_distinct")
    if progress_bar_for_each_datapoint:
        cmd.append("--progress_bar_for_each_datapoint")

    # 서브프로세스로 평가 스크립트를 실행하고, 출력에서 정확도를 추출합니다.
    proc = subprocess.run(cmd, capture_output=True, text=True)
    accuracy = _parse_testsuite_accuracy(proc.stdout)

    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "execution_accuracy": accuracy,
        "command": cmd,
    }

#
def load_json_results(path: str | Path) -> list[dict[str, Any]]:
    """results.json을 로드합니다."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("results JSON은 리스트 형식이어야 합니다.")
    return data

