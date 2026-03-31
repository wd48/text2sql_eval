import json
import csv
import sqlite3
# Spider 데이터셋 경로 설정
SPIDER_PATH = Path(__file__).parent / "spider"

print("🚀 Spider 데이터셋에서 questions.csv 생성 중...\n")

# dev.json에서 질문 데이터 로드
try:
    with open(SPIDER_PATH / "dev.json", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✓ 로드된 질문: {len(data)}개\n")
except FileNotFoundError:
    print(f"❌ 오류: {SPIDER_PATH / 'dev.json'}를 찾을 수 없습니다.")
    print(f"   Spider 데이터셋이 {SPIDER_PATH}에 있는지 확인하세요.")
    exit(1)

# questions.csv 생성 (main.py의 load_questions와 호환되는 포맷)
# 컬럼: question, schema, gold_sql, db_name, db_type
with open("questions.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["question", "schema", "gold_sql", "db_name", "db_type"])
    writer.writeheader()

    processed = 0
    skipped = 0
    
    print("처리 중...")
    for item in data[:20]:  # 테스트용 처음 20개
        db_id = item["db_id"]
        # Spider 표준 경로: spider/database/{db_name}/{db_name}.sqlite
        db_path = SPIDER_PATH / "database" / db_id / f"{db_id}.sqlite"

        try:
            # 데이터베이스 연결 및 스키마 추출
            conn = sqlite3.connect(str(db_path))
            schema_parts = []
            
            # 모든 테이블 정보 추출
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            
            for (tname,) in tables:
                # 각 테이블의 컬럼 정보 추출
                cols = conn.execute(f"PRAGMA table_info({tname})").fetchall()
                col_info = [f"{c[1]}({c[2]})" for c in cols]  # 컬럼명(타입)
                schema_parts.append(f"Table: {tname}, Columns: [{', '.join(col_info)}]")
            
            conn.close()

            # CSV 행 작성
            writer.writerow({
                "question": item["question"],
                "schema":   " | ".join(schema_parts),  # 모든 테이블 스키마
                "gold_sql": item["query"],              # SQL 쿼리
                "db_name":  db_id,                      # 데이터베이스 이름 (평가 시 DB 파일 경로에 사용)
                "db_type":  "sqlite"                     # 데이터베이스 타입
            })
            processed += 1
            print(f"  ✓ [{processed:2d}] {db_id:20s} | {item['question'][:50]}...")
            
        except FileNotFoundError:
            skipped += 1
            print(f"  ✗ [{skipped:2d}] {db_id:20s} | DB 파일 없음: {db_path}")
        except sqlite3.Error as e:
            skipped += 1
            print(f"  ✗ [{skipped:2d}] {db_id:20s} | SQLite 오류: {str(e)[:50]}")
        except Exception as e:
            skipped += 1
            print(f"  ✗ [{skipped:2d}] {db_id:20s} | 오류: {str(e)[:50]}")

print(f"\n{'='*70}")
print(f"✓ questions.csv 생성 완료!")
print(f"  처리됨: {processed}개")
print(f"  건너뜀: {skipped}개")
print(f"{'='*70}\n")
print("💡 다음 명령으로 실행하세요:")
print("   python main.py -m llama3-langchain -q questions.csv")
