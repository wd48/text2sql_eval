import argparse
# 기존 Runner import 생략
from runners.langchain_runner import LangChainOllamaRunner


def main():
    parser = argparse.ArgumentParser(description="Run SQL Evaluation")
    parser.add_argument("-m", "--model", type=str, required=True, help="Model to use (e.g., gpt-4, llama3-langchain)")
    parser.add_argument("-q", "--questions_file", type=str, required=True, help="Path to questions CSV")
    # 기타 argument 생략...
    args = parser.parse_args()

    # Runner Factory 패턴 적용
    if args.model == "llama3-langchain":
        runner = LangChainOllamaRunner(model_name="llama3")
    elif args.model == "gpt-4":
        pass  # 기존 OpenAI Runner 로직
    else:
        raise ValueError(f"Unsupported model: {args.model}")

    # 데이터셋 로드 및 SQL 생성 루프 (sql-eval 기존 로직)
    # questions = load_questions(args.questions_file)
    # for q in questions:
    #     predicted_sql = runner.generate_sql(q['question'], q['schema'])
    #     save_result(predicted_sql)


if __name__ == "__main__":
    main()