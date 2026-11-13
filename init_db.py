"""DB 연결 확인 + 없는 테이블만 생성한다.

- 기존 테이블/데이터는 삭제(DROP)하거나 수정(ALTER)하지 않는다.
- 같은 이름의 테이블이 이미 있는데 컬럼이 다르면, 알려주기만 하고 멈춘다.

실행: .\\.venv\\Scripts\\python.exe init_db.py
"""

import sys

from sqlalchemy import inspect, text

import models  # noqa: F401  (테이블 정의 등록)
from database import Base, engine


def main() -> int:
    print("접속 대상:", engine.url.render_as_string(hide_password=True))
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT VERSION()")).scalar()
            database = connection.execute(text("SELECT DATABASE()")).scalar()
    except Exception as error:  # 비밀번호가 출력되지 않도록 오류 종류만 보여준다.
        print("DB 연결 실패:", type(error).__name__)
        print("MySQL 실행 여부, .env의 DB_USER/DB_PASSWORD/DB_NAME, 계정 권한을 확인해주세요.")
        return 1
    print(f"연결 성공: MySQL {version}, DB={database}")

    existing = set(inspect(engine).get_table_names())
    problems = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue
        actual = {column["name"] for column in inspect(engine).get_columns(table.name)}
        missing = {column.name for column in table.columns} - actual
        if missing:
            problems.append(f"- {table.name} 테이블에 없는 컬럼: {', '.join(sorted(missing))}")
        else:
            print(f"이미 있음(그대로 사용): {table.name}")
    if problems:
        print("기존 테이블 구조가 이 앱과 다릅니다. 자동으로 바꾸지 않았습니다.")
        print("\n".join(problems))
        print("다른 DB 이름(DB_NAME)을 쓰거나, 기존 테이블을 직접 확인한 뒤 정리해주세요.")
        return 1

    to_create = [table for table in Base.metadata.sorted_tables if table.name not in existing]
    Base.metadata.create_all(engine, tables=to_create, checkfirst=True)
    for table in to_create:
        print(f"새로 생성: {table.name}")
    print("준비 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
