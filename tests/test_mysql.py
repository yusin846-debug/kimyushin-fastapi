"""실제 MySQL 통합 테스트. .env에 TEST_DB_NAME(이름에 test 포함)이 있을 때만 실행된다.

테스트 전용 DB에 테이블을 만들고, 끝나면 그 DB의 테이블만 삭제한다. 실제 DB(DB_NAME)는 건드리지 않는다.
"""

import os
import unittest

from sqlalchemy import text

from database import make_engine
from helpers import AppTestMixin

TEST_DB_NAME = os.getenv("TEST_DB_NAME", "")
SAFE = "test" in TEST_DB_NAME.lower() and TEST_DB_NAME != os.getenv("DB_NAME", "fastapi_db")


@unittest.skipUnless(SAFE, "TEST_DB_NAME(예: fastapi_test_db)이 설정되지 않아 MySQL 테스트를 건너뜁니다.")
class MySqlIntegrationTests(AppTestMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = make_engine(TEST_DB_NAME)
        with cls.engine.connect() as connection:
            tables = connection.execute(text("SHOW TABLES")).scalars().all()
        if tables:
            raise unittest.SkipTest(f"{TEST_DB_NAME}에 이미 테이블이 있어 안전을 위해 건너뜁니다: {tables}")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_full_flow_on_mysql(self):
        user_id = self.create_user()
        self.assertEqual(self.client.post("/users", json={"name": "x", "email": "yusin@example.com"}).status_code, 409)
        self.assertEqual(self.upload("한글 파일.txt", "안녕".encode(), 999).status_code, 404)

        response = self.upload("한글 파일.txt", "안녕".encode(), user_id)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.upload("한글 파일.txt", b"other", user_id).status_code, 409)

        listed = self.client.get("/files").json()
        self.assertEqual([(f["filename"], f["user_id"]) for f in listed["files"]], [("한글 파일.txt", user_id)])
        self.assertEqual(self.client.get("/download", params={"filename": "한글 파일.txt"}).content, "안녕".encode())

        # 새 세션(=서버 재시작 후와 같은 상황)에서도 데이터가 남아 있는지 확인
        self.engine.dispose()
        self.assertEqual(self.client.get(f"/users/{user_id}").json()["name"], "김유신")
        self.assertEqual(self.client.get("/files").json()["count"], 1)


if __name__ == "__main__":
    unittest.main()
