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
    # eval.py에서 평가 관련 함수 임포트
    # eval.py가 없거나 의존성 문제로 임포트 실패할 경우, 평가 기능을 비활성화하고 경고 메시지를 출력합니다.
    from eval.eval import (
        build_testsuite_eval_inputs,
        evaluate_execution_accuracy,
        normalize_classification_label,
        run_testsuite_eval,
        sanitize_sql,
    )
except ImportError:
    build_testsuite_eval_inputs = None
    evaluate_execution_accuracy = None
    run_testsuite_eval = None
    normalize_classification_label = lambda text: text or "Unknown"
    sanitize_sql = lambda text: (text or "").strip()

# 프로젝트 루트 경로 설정 (spider 데이터셋 위치)
PROJECT_ROOT = Path(__file__).parent
SPIDER_DB_PATH = PROJECT_ROOT / "spider" / "database"
TESTSUITE_DB_PATH = PROJECT_ROOT / "eval" / "test-suite-sql-eval" / "database"
TESTSUITE_TABLE_PATH = PROJECT_ROOT / "eval" / "test-suite-sql-eval" / "tables.json"

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
    # classification_result 또는 classification_label에서 라벨을 추출 > 정규화한 후 통계 계산
    labels = [normalize_classification_label(r.get("classification_result") or r.get("classification_label") or "Unknown") for r in results]
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
    # 모델과 질문 파일은 필수, 출력 파일과 평가 옵션은 선택사항으로 설정
    parser.add_argument("-m", "--model",          type=str, required=True,
                        help="사용할 모델 (예: llama3-langchain)")
    parser.add_argument("-q", "--questions_file", type=str, required=True,
                        help="질문 CSV 파일 경로")
    parser.add_argument("-o", "--output",         type=str, default="results.json",
                        help="출력 JSON 파일 경로 (기본값: results.json)")
    parser.add_argument("--no-eval",             action="store_true",
                        help="평가 단계 스킵 (SQL 생성만 수행)")
    parser.add_argument("--eval-backend",        type=str, default="simple",
                        choices=("simple", "testsuite", "both"),
                        help="평가 백엔드 선택 (기본값: simple)")
    parser.add_argument("--eval-artifact-dir",   type=str, default="artifacts",
                        help="test-suite용 gold/pred 출력 디렉터리")
    parser.add_argument("--testsuite-db-root",    type=str, default=str(TESTSUITE_DB_PATH),
                        help="test-suite DB 루트 경로")
    parser.add_argument("--testsuite-table",      type=str, default=str(TESTSUITE_TABLE_PATH),
                        help="test-suite tables.json 경로")
    
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
        # 생성된 SQL과 gold SQL을 정제하여 비교하기 쉽게 만듭니다. (공백 제거, 코드펜스 제거 등)
        predicted_sql = sanitize_sql(generation["predicted_sql"])
        gold_sql = sanitize_sql(q.get("gold_sql", ""))
        
        results.append({
            "question":      q["question"],
            "schema":        q.get("schema", ""),
            "db_name":       q.get("db_name", ""),
            "predicted_sql": predicted_sql,
            "gold_sql":      gold_sql,
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
            # eval.py에서 필요한 함수들이 임포트되었는지 확인
            if evaluate_execution_accuracy is None or build_testsuite_eval_inputs is None or run_testsuite_eval is None:
                raise ImportError("eval.py를 임포트할 수 없습니다.")
            # 평가 백엔드에 따라 simple execution 평가, test-suite 평가 또는 둘 다 수행
            if args.eval_backend in ("simple", "both"):
                print("📊 simple execution evaluation")
                correct_count = 0
                skipped_count = 0

                # 각 결과에 대해 gold SQL과 predicted SQL을 실행하여 정확도 계산
                for idx, result in enumerate(results):
                    db_name = result.get("db_name", "")
                    gold_sql = sanitize_sql(result.get("gold_sql", ""))
                    predicted_sql = sanitize_sql(result.get("predicted_sql", ""))
                    # DB 파일 경로 구성: SPIDER_DB_PATH / db_name / db_name.sqlite
                    if db_name:
                        db_file = SPIDER_DB_PATH / db_name / f"{db_name}.sqlite"
                        db_file_str = str(db_file)
                    else:
                        db_file_str = ""

                    # DB 파일이 존재하고 gold_sql과 predicted_sql이 모두 존재하는 경우에만 평가, 그렇지 않으면 스킵
                    if db_file_str and os.path.exists(db_file_str) and gold_sql and predicted_sql:
                        try:
                            # evaluate_execution_accuracy
                            # predicted_sql과 gold_sql을 실행하여 결과가 같은지 비교하는 함수입니다.
                            is_correct = evaluate_execution_accuracy(db_file_str, predicted_sql, gold_sql)
                            result["is_correct_simple"] = is_correct
                            result["is_correct"] = is_correct
                            if is_correct:
                                correct_count += 1
                            status = "✓" if is_correct else "✗"
                            print(f"  [{idx+1}] {status} {result['question'][:50]}...")
                        except Exception as e:
                            result["is_correct_simple"] = False
                            result["is_correct"] = False
                            result["error_simple"] = str(e)[:100]
                            print(f"  [{idx+1}] ✗ {result['question'][:50]}... (오류: {str(e)[:40]})")
                    else:
                        # DB 파일이 없거나 gold_sql/predicted_sql이 없는 경우 평가를 스킵하고 이유를 로그에 남깁니다.
                        skipped_count += 1
                        result["is_correct_simple"] = False
                        result["is_correct"] = False
                        reason = ""
                        if not db_name:
                            reason = "db_name 없음"
                        elif not os.path.exists(db_file_str):
                            reason = "DB 파일 없음"
                        elif not gold_sql:
                            reason = "gold_sql 없음"
                        print(f"  [{idx+1}] ⚠️  {result['question'][:50]}... ({reason})")
                # 평가 결과 요약 출력
                total = len(results)
                accuracy_pct = (correct_count / total * 100) if total > 0 else 0
                print(f"\n{'='*60}")
                print("📈 simple execution 결과:")
                print(f"   전체 질문: {total}")
                print(f"   정답: {correct_count}")
                print(f"   스킵: {skipped_count}")
                print(f"   정확도: {accuracy_pct:.2f}%")
                print(f"{'='*60}\n")
            # test-suite 평가 준비 및 실행
            if args.eval_backend in ("testsuite", "both"):
                print("📦 test-suite evaluation 준비")
                artifact_dir = PROJECT_ROOT / args.eval_artifact_dir
                testsuite_db_root = Path(args.testsuite_db_root)
                testsuite_table_path = Path(args.testsuite_table)

                build_info = build_testsuite_eval_inputs(results, artifact_dir, testsuite_db_root)
                gold_path = build_info["gold_path"]
                pred_path = build_info["pred_path"]

                if build_info["line_count"] == 0:
                    raise RuntimeError("test-suite 평가용 입력이 0건입니다. db_name/test-suite DB 매핑을 확인하세요.")

                print(f"   gold: {gold_path}")
                print(f"   pred: {pred_path}")
                print(f"   line_count: {build_info['line_count']}")
                print(f"   skipped_no_db: {build_info['skipped_no_db']}")
                print(f"   skipped_empty: {build_info['skipped_empty']}")

                if build_info["line_count"] != sum(1 for _ in open(gold_path, encoding="utf-8")):
                    raise RuntimeError("gold 파일 라인 수가 예상과 다릅니다.")
                if build_info["line_count"] != sum(1 for _ in open(pred_path, encoding="utf-8")):
                    raise RuntimeError("pred 파일 라인 수가 예상과 다릅니다.")
                # test-suite 평가 실행
                suite_result = run_testsuite_eval(
                    gold_path=gold_path,
                    pred_path=pred_path,
                    db_root=testsuite_db_root,
                    table_path=testsuite_table_path if testsuite_table_path.exists() else None,
                    etype="exec",
                    plug_value=True,
                    keep_distinct=False,
                    progress_bar_for_each_datapoint=False,
                )

                print("\n" + suite_result["stdout"])
                if suite_result["stderr"]:
                    print("[stderr]\n" + suite_result["stderr"])
                if suite_result["returncode"] != 0:
                    raise RuntimeError(f"test-suite 평가 실패 (returncode={suite_result['returncode']})")

                if suite_result["execution_accuracy"] is not None:
                    print(f"test-suite overall execution accuracy: {suite_result['execution_accuracy']:.3f}")

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