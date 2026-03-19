import json
import csv
import sqlite3

SPIDER_PATH = "spider_data"  # Spider 압축 해제 경로

with open(f"{SPIDER_PATH}/dev.json", encoding="utf-8") as f:
    data = json.load(f)

with open("questions.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["question", "schema", "gold_sql"])
    writer.writeheader()

    for item in data[:20]:  # 테스트용 20개
        db_id = item["db_id"]
        db_path = f"{SPIDER_PATH}/database/{db_id}/{db_id}.db"

        try:
            conn = sqlite3.connect(db_path)
            schema_parts = []
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            for (tname,) in tables:
                cols = [
                    c[1] for c in conn.execute(f"PRAGMA table_info({tname})").fetchall()
                ]
                schema_parts.append(f"Table: {tname}, Columns: {cols}")
            conn.close()

            writer.writerow({
                "question": item["question"],
                "schema":   " | ".join(schema_parts),
                "gold_sql": item["query"]
            })
        except Exception as e:
            print(f"[SKIP] {db_id}: {e}")

print("questions.csv 생성 완료")