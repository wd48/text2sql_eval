import argparse
import csv
import json
import os

# GPU 활성화: Ollama가 GPU를 사용하도록 설정
# OLLAMA_NUM_GPU=-1: 모든 모델 레이어를 GPU에 로드 (CUDA/ROCm이 설치된 경우 자동 사용)
if not os.environ.get('OLLAMA_NUM_GPU'):
    os.environ['OLLAMA_NUM_GPU'] = '-1'

from runners.langchain_runner import LangChainOllamaRunner

def load_questions(filepath: str) -> list:
    questions = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # CSV 컬럼: db_name, db_type, query_category, query, question, instructions
            questions.append({
                "question": row.get("question", ""),
                "db_name": row.get("db_name", ""),
                "db_type": row.get("db_type", ""),
                "gold_sql": row.get("query", "").split(";")[0].strip(),  # 첫 번째 쿼리만
                "instructions": row.get("instructions", "")
            })
    return questions


def save_result(results: list, output_path: str = "results.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"결과 저장 완료 → {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run SQL Evaluation")
    parser.add_argument("-m", "--model",          type=str, required=True)
    parser.add_argument("-q", "--questions_file", type=str, required=True)
    args = parser.parse_args()

    if args.model == "llama3-langchain":
        runner = LangChainOllamaRunner(model_name="gemma3n:latest")
    else:
        raise ValueError(f"Unsupported model: {args.model}")

    questions = load_questions(args.questions_file)
    results = []
    for i, q in enumerate(questions):
        print(f"[{i+1}/{len(questions)}] {q['question']}")

        # schema가 없으면 db_type 또는 기본값 사용
        schema = q.get("schema", f"Database: {q.get('db_name', 'unknown')} ({q.get('db_type', 'sqlite')})")

        predicted_sql = runner.generate_sql(q["question"], schema)
        results.append({
            "question":      q["question"],
            "db_name":       q.get("db_name", ""),
            "predicted_sql": predicted_sql,
            "gold_sql":      q.get("gold_sql", "")
        })
        print(f"  → {predicted_sql}\n")

    save_result(results)


if __name__ == "__main__":
    main()