import argparse
import csv
import json
import re
from pathlib import Path


def clean_sql(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^\s*`{1,3}\s*[a-zA-Z0-9_-]*\s*\n?", "", s)
    s = re.sub(r"\n?\s*`{1,3}\s*$", "", s)
    s = re.sub(r"^(sqlite|sql|ite)\b\s*", "", s, flags=re.IGNORECASE)
    # test-suite 입력은 1라인 1쿼리 형식이므로 줄바꿈을 공백으로 평탄화
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="questions.csv + results.json -> test-suite gold/pred 생성")
    parser.add_argument("--questions", default="questions.csv", help="questions CSV 경로")
    parser.add_argument("--results", default="results.json", help="results JSON 경로")
    parser.add_argument("--db-root", default="eval/test-suite-sql-eval/database", help="test-suite DB 루트")
    parser.add_argument("--out-dir", default="artifacts", help="출력 디렉터리")
    parser.add_argument("--gold-name", default="testsuite_gold.txt", help="gold 출력 파일명")
    parser.add_argument("--pred-name", default="testsuite_pred.txt", help="pred 출력 파일명")
    args = parser.parse_args()

    root = Path(__file__).parent
    questions_path = (root / args.questions).resolve()
    results_path = (root / args.results).resolve()
    db_root = (root / args.db_root).resolve()
    out_dir = (root / args.out_dir).resolve()
    out_gold = out_dir / args.gold_name
    out_pred = out_dir / args.pred_name

    available_db = {p.name for p in db_root.iterdir() if p.is_dir()}

    with questions_path.open("r", encoding="utf-8") as f:
        q_rows = list(csv.DictReader(f))
    with results_path.open("r", encoding="utf-8") as f:
        r_rows = json.load(f)

    if len(q_rows) != len(r_rows):
        print(f"WARN: questions({len(q_rows)}) != results({len(r_rows)}), zip 최소 길이로 처리")

    pairs = []
    skipped_no_db = 0
    skipped_empty = 0

    for q, r in zip(q_rows, r_rows):
        db_id = (q.get("db_name") or r.get("db_name") or "").strip()
        if not db_id or db_id not in available_db:
            skipped_no_db += 1
            continue

        gold = clean_sql(q.get("gold_sql") or r.get("gold_sql") or "")
        pred = clean_sql(r.get("predicted_sql") or "")

        if not gold or not pred:
            skipped_empty += 1
            continue

        pairs.append((f"{gold}\t{db_id}", pred))

    out_dir.mkdir(parents=True, exist_ok=True)
    with out_gold.open("w", encoding="utf-8", newline="\n") as fg, out_pred.open("w", encoding="utf-8", newline="\n") as fp:
        for g, p in pairs:
            fg.write(g + "\n")
            fp.write(p + "\n")

    print(f"generated={len(pairs)}")
    print(f"skipped_no_db={skipped_no_db}")
    print(f"skipped_empty={skipped_empty}")
    print(f"gold={out_gold}")
    print(f"pred={out_pred}")


if __name__ == "__main__":
    main()

