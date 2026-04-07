import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

# GPU 활성화: Ollama가 GPU를 사용하도록 설정
# OLLAMA_NUM_GPU=-1: 모든 모델 레이어를 GPU에 로드 (CUDA/ROCm이 설치된 경우 자동 사용)
if not os.environ.get('OLLAMA_NUM_GPU'):
    os.environ['OLLAMA_NUM_GPU'] = '-1'

from runners.langchain_runner import LangChainOllamaRunner

try:
    from eval.eval import evaluate_execution_accuracy
except ImportError:
    evaluate_execution_accuracy = None

# 프로젝트 루트 경로 설정 (spider 데이터셋 위치)
PROJECT_ROOT = Path(__file__).parent
SPIDER_DB_PATH = PROJECT_ROOT / "spider" / "database"

def load_questions(filepath: str) -> list:
    """
    CSV 파일에서 질문 데이터 로드
    기대 컬럼: question, schema, gold_sql, db_name (선택), db_type (선택)
    """
    questions = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # gold_sql이 여러 쿼리인 경우 첫 번째만 사용
            gold_sql = row.get("gold_sql", "").split(";")[0].strip()
            
            questions.append({
                "question": row.get("question", ""),
                "schema": row.get("schema", ""),
                "db_name": row.get("db_name", ""),
                "db_type": row.get("db_type", "sqlite"),
                "gold_sql": gold_sql
            })
    return questions


def save_result(results: list, output_path: str = "results.json"):
    """결과를 JSON 형식으로 저장"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✓ 결과 저장 완료 → {output_path}")


# 2026-04-07 SQL 생성 루프 종료 직후 통계 출력 호출 추가
def print_classification_stats(results: list):
    """classification_label 기준 통계와 Unanswerable 비율 출력"""
    total = len(results)
    labels = [r.get("classification_label", "Unknown") or "Unknown" for r in results]
    counts = Counter(labels)
    unanswerable_count = counts.get("Unanswerable", 0)
    unanswerable_ratio = (unanswerable_count / total * 100) if total > 0 else 0.0

    print(f"\n{'='*60}")
    print("📊 분류 라벨 통계:")
    print(f"   전체 질문: {total}")
    for label in ("Answerable", "Ambiguous", "Unanswerable", "Unknown"):
        if label in counts:
            print(f"   {label}: {counts[label]}")
    print(f"   Unanswerable 비율: {unanswerable_ratio:.2f}%")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Text-to-SQL 평가 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python main.py -m llama3-langchain -q questions.csv
  python main.py -m llama3-langchain -q questions.csv -o results.json
        """
    )
    parser.add_argument("-m", "--model",          type=str, required=True,
                        help="사용할 모델 (예: llama3-langchain)")
    parser.add_argument("-q", "--questions_file", type=str, required=True,
                        help="질문 CSV 파일 경로")
    parser.add_argument("-o", "--output",         type=str, default="results.json",
                        help="출력 JSON 파일 경로 (기본값: results.json)")
    parser.add_argument("--no-eval",             action="store_true",
                        help="평가 단계 스킵 (SQL 생성만 수행)")
    
    args = parser.parse_args()

    # 모델 초기화
    if args.model == "llama3-langchain":
        print("🚀 모델 초기화: LangChain + Ollama (GPU 모드)")
        try:
            runner = LangChainOllamaRunner(model_name="gemma3n:latest")
        except Exception as e:
            print(f"❌ 오류: Ollama 모델을 찾을 수 없습니다. {e}")
            print("   해결방법:")
            print("   1. Ollama 설치: https://ollama.ai")
            print("   2. 모델 다운로드: ollama pull gemma3n:latest")
            raise SystemExit(1)
    else:
        raise ValueError(f"지원하지 않는 모델: {args.model}")

    # 질문 로드
    print(f"\n📂 질문 파일 로드: {args.questions_file}")
    questions = load_questions(args.questions_file)
    print(f"   → {len(questions)}개 질문 로드됨\n")

    # SQL 생성 단계
    print(f"🔄 SQL 생성 단계 시작...\n")
    results = []
    
    for i, q in enumerate(questions):
        print(f"[{i+1}/{len(questions)}] {q['question']}")
        
        # schema 사용 (CSV에 있으면 사용, 없으면 db_name으로 구성)
        schema = q.get("schema", "")
        if not schema and q.get("db_name"):
            schema = f"Database: {q.get('db_name')} ({q.get('db_type', 'sqlite')})"

        generation = runner.generate_sql(q["question"], schema, return_metadata=True)
        predicted_sql = generation["predicted_sql"]
        
        results.append({
            "question":      q["question"],
            "schema":        q.get("schema", ""),
            "db_name":       q.get("db_name", ""),
            "predicted_sql": predicted_sql,
            "gold_sql":      q.get("gold_sql", ""),
            "db_type":       q.get("db_type", "sqlite"),
            "classification_result": generation.get("classification_result", ""),
            "classification_label": generation.get("classification_label", "Unknown"),
            "linked_schema": generation.get("linked_schema", ""),
            "draft_sql": generation.get("draft_sql", "")
        })
        print(f"  → [{generation.get('classification_label', 'Unknown')}] {predicted_sql[:80]}...\n")

    print_classification_stats(results)

    # 평가 단계 (선택사항)
    if not args.no_eval:
        print("\n📊 평가 단계 시작...\n")
        try:
            if evaluate_execution_accuracy is None:
                raise ImportError("eval.py를 임포트할 수 없습니다.")

            correct_count = 0
            
            for idx, result in enumerate(results):
                db_name = result.get("db_name", "")
                gold_sql = result.get("gold_sql", "")
                predicted_sql = result.get("predicted_sql", "")
                
                # DB 파일 경로 구성
                if db_name:
                    db_file = SPIDER_DB_PATH / db_name / f"{db_name}.sqlite"
                    db_file_str = str(db_file)
                else:
                    db_file_str = ""
                
                # 평가 수행
                if db_file_str and os.path.exists(db_file_str) and gold_sql and predicted_sql:
                    try:
                        is_correct = evaluate_execution_accuracy(
                            db_file_str,
                            predicted_sql,
                            gold_sql
                        )
                        result["is_correct"] = is_correct
                        if is_correct:
                            correct_count += 1
                        status = "✓" if is_correct else "✗"
                        print(f"  [{idx+1}] {status} {result['question'][:50]}...")
                    except Exception as e:
                        result["is_correct"] = False
                        result["error"] = str(e)[:100]
                        print(f"  [{idx+1}] ✗ {result['question'][:50]}... (오류: {str(e)[:40]})")
                else:
                    result["is_correct"] = False
                    reason = ""
                    if not db_name:
                        reason = "db_name 없음"
                    elif not os.path.exists(db_file_str):
                        reason = "DB 파일 없음"
                    elif not gold_sql:
                        reason = "gold_sql 없음"
                    print(f"  [{idx+1}] ⚠️  {result['question'][:50]}... ({reason})")
            
            # 최종 통계
            total = len(results)
            accuracy_pct = (correct_count / total * 100) if total > 0 else 0
            print(f"\n{'='*60}")
            print(f"📈 최종 평가 결과:")
            print(f"   전체 질문: {total}")
            print(f"   정답: {correct_count}")
            print(f"   정확도: {accuracy_pct:.2f}%")
            print(f"{'='*60}\n")

        except ImportError:
            print("⚠️  경고: eval.py를 임포트할 수 없습니다.")
            print("   --no-eval 옵션으로 평가 단계를 스킵할 수 있습니다.\n")
        except Exception as e:
            print(f"⚠️  평가 단계 중 오류 발생: {e}\n")

    # 결과 저장
    save_result(results, args.output)
    
    print("✅ 작업 완료!")


if __name__ == "__main__":
    main()