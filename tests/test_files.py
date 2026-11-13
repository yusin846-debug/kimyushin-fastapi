import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main
from helpers import AppTestMixin
from models import FileRecord


def sqlite_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    return engine


class FileApiTests(AppTestMixin, unittest.TestCase):
    engine = sqlite_engine()

    # ---------------- 유저
    def test_user_create_list_detail(self):
        user_id = self.create_user(email="  Yusin@Example.com ")
        detail = self.client.get(f"/users/{user_id}").json()
        self.assertEqual((detail["name"], detail["email"]), ("김유신", "yusin@example.com"))
        self.assertIn("created_at", detail)
        self.assertEqual([u["id"] for u in self.client.get("/users").json()], [user_id])

    def test_user_errors(self):
        self.create_user()
        self.assertEqual(self.client.post("/users", json={"name": "다른 사람", "email": "YUSIN@example.com"}).status_code, 409)
        self.assertEqual(self.client.get("/users/999").status_code, 404)
        for body in [{"name": "", "email": "a@b.co"}, {"name": "a", "email": "not-email"}, {"name": "a"}]:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/users", json=body).status_code, 422)

    # ---------------- 파일
    def test_upload_list_download_korean_file(self):
        user_id = self.create_user()
        self.assertEqual(self.client.get("/files").json(), {"count": 0, "files": [], "unregistered_files": []})
        data = "안녕하세요".encode()
        response = self.upload("한글 파일.txt", data, user_id)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user_id"], user_id)
        files = self.client.get("/files").json()["files"]
        self.assertEqual([(f["filename"], f["size"], f["user_id"]) for f in files],
                         [("한글 파일.txt", len(data), user_id)])
        response = self.client.get("/download", params={"filename": "한글 파일.txt"})
        self.assertEqual(response.content, data)
        self.assertIn("attachment", response.headers["content-disposition"])

    def test_duplicate_preserves_original(self):
        user_id = self.create_user()
        self.upload("test.txt", b"first", user_id)
        self.assertEqual(self.upload("test.txt", b"second", user_id).status_code, 409)
        self.assertEqual((self.directory / "test.txt").read_bytes(), b"first")
        self.assertEqual(len(list(self.directory.iterdir())), 1)
        self.assertEqual(self.client.get("/files").json()["count"], 1)

    def test_existing_disk_file_without_metadata_is_kept(self):
        user_id = self.create_user()
        (self.directory / "old.txt").write_bytes(b"old")
        self.assertEqual(self.client.get("/files").json()["unregistered_files"], ["old.txt"])
        self.assertEqual(self.upload("old.txt", b"new", user_id).status_code, 409)
        self.assertEqual((self.directory / "old.txt").read_bytes(), b"old")
        self.assertEqual(self.client.get("/download", params={"filename": "old.txt"}).content, b"old")

    def test_unknown_user_rejected(self):
        response = self.upload("a.txt", b"x", 999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_db_commit_failure_cleans_new_file(self):
        user_id = self.create_user()
        (self.directory / "keep.txt").write_bytes(b"keep")
        for error, status in [(OperationalError("x", {}, Exception()), 503),
                              (IntegrityError("x", {}, Exception()), 409)]:
            with self.subTest(error=type(error).__name__):
                with patch.object(Session, "commit", side_effect=error):
                    self.assertEqual(self.upload("new.txt", b"data", user_id).status_code, status)
                self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ["keep.txt"])
        with self.Session() as db:
            self.assertEqual(db.query(FileRecord).count(), 0)

    def test_invalid_names(self):
        user_id = self.create_user()
        for name in ["../secret.txt", "..\\secret.txt", ".env", "a:b", "NUL.txt"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get("/download", params={"filename": name}).status_code, 400)
                self.assertEqual(self.upload(name, b"x", user_id).status_code, 400)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_missing_file_and_required_parameters(self):
        user_id = self.create_user()
        self.assertEqual(self.client.get("/download", params={"filename": "missing.txt"}).status_code, 404)
        self.assertEqual(self.client.get("/download").status_code, 422)
        self.assertEqual(self.client.post("/upload").status_code, 422)
        self.assertEqual(self.client.post("/upload", files={"file": ("a.txt", b"x")}).status_code, 422)
        self.assertEqual(self.client.post("/upload", data={"user_id": str(user_id)}).status_code, 422)

    def test_size_limit_cleans_up(self):
        user_id = self.create_user()
        with patch.object(main, "MAX_FILE_SIZE", 3):
            self.assertEqual(self.upload("big.txt", b"1234", user_id).status_code, 413)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_symlinks_are_hidden_and_rejected(self):
        try:
            (self.directory / "alias.txt").symlink_to(Path(main.__file__))
        except OSError:
            self.skipTest("이 PC에서는 심볼릭 링크 생성 권한이 없습니다(Windows 기본 설정).")
        self.assertEqual(self.client.get("/files").json()["unregistered_files"], [])
        self.assertEqual(self.client.get("/download", params={"filename": "alias.txt"}).status_code, 400)

    def test_docs_and_schema(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(set(schema["paths"]), {"/upload", "/download", "/files", "/users", "/users/{user_id}"})
        self.assertIn("multipart/form-data", schema["paths"]["/upload"]["post"]["requestBody"]["content"])


if __name__ == "__main__":
    unittest.main()
