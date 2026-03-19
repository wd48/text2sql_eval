import sqlite3
import pandas as pd

""" SQL 실행 정확도 평가 모듈
- 예측된 SQL과 정답 SQL을 실제 DB에서 실행하여 결과 셋이 동일한지 검증하는 기능을 제공합니다.
- SQL 문법 오류, 존재하지 않는 테이블/컬럼 참조 등의 에러 발생 시 False로 처리하여 모델의 실행 가능 여부를 평가합니다.
- 전체 결과 데이터프레임을 순회하며 정확도를 계산하는 함수도 포함되어 있습니다. (results_df는 'gold_sql'과 'predicted_sql' 컬럼을 가지고 있어야 함)
"""
# https://github.com/taoyds/test-suite-sql-eval
def evaluate_execution_accuracy(db_path: str, predicted_sql: str, gold_sql: str) -> bool:
    """
    예측된 SQL과 정답 SQL을 실제 DB에서 실행하고, 결과 셋이 동일한지 검증합니다.
    """
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
        # print(f"[Eval Error] {e} | SQL: {predicted_sql}")
        return False
    except Exception as e:
        return False


def run_evaluation_suite(results_df: pd.DataFrame, db_path: str) -> dict:
    """
    전체 결과 데이터프레임을 순회하며 정확도를 계산합니다.
    (results_df는 'gold_sql'과 'predicted_sql' 컬럼을 가지고 있어야 함)
    """
    total = len(results_df)
    correct = 0

    for idx, row in results_df.iterrows():
        is_correct = evaluate_execution_accuracy(db_path, row['predicted_sql'], row['gold_sql'])
        if is_correct:
            correct += 1

    accuracy = (correct / total) * 100 if total > 0 else 0.0

    return {
        "total_queries": total,
        "correct_queries": correct,
        "execution_accuracy": f"{accuracy:.2f}%"
    }