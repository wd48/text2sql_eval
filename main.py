import argparse

"""CLI entry point for SQL Evaluation. 
기존 sql-eval의 main.py를 리팩토링하여 Runner Factory 패턴을 적용하고, 모델별 Runner를 유연하게 선택할 수 있도록 개선합니다. 
기존 OpenAI Runner 로직은 유지하되, 새로운 LangChain Ollama Runner를 추가하여 다양한 모델을 지원할 수 있도록 확장성을 확보합니다."""

def main():
    parser = argparse.ArgumentParser(description="Run SQL Evaluation")
    parser.add_argument("-m", "--model", type=str, required=True, help="Model to use (e.g., gpt-4, llama3-langchain)")
    parser.add_argument("-q", "--questions_file", type=str, required=True, help="Path to questions CSV")
    # 기타 argument 생략...
    args = parser.parse_args()

    # Runner Factory 패턴 적용
    if args.model == "llama3-langchain":
        # LangChain 계열 의존성은 해당 모델 사용 시점에만 로드합니다.
        from runners.langchain_runner import LangChainOllamaRunner
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