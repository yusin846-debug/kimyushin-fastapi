"""테스트 공통 준비: 임시 폴더 + 테스트 전용 DB를 앱에 연결한다. 실제 파일·DB는 건드리지 않는다."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import main
from database import Base, get_db


class AppTestMixin:
    engine = None  # 하위 클래스에서 지정

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        patcher = patch.object(main, "FILES_DIR", self.directory)
        patcher.start()
        self.addCleanup(patcher.stop)

        Base.metadata.create_all(self.engine)
        self.addCleanup(Base.metadata.drop_all, self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[get_db] = override_get_db
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def create_user(self, name="김유신", email="yusin@example.com"):
        response = self.client.post("/users", json={"name": name, "email": email})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def upload(self, name, data, user_id):
        return self.client.post("/upload", files={"file": (name, data)}, data={"user_id": str(user_id)})
