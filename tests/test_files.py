import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import main


class FileApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.patcher = patch.object(main, "FILES_DIR", self.directory)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_upload_list_download_korean_file(self):
        self.assertEqual(self.client.get("/files").json(), {"count": 0, "files": []})
        data = "안녕하세요".encode()
        response = self.client.post("/upload", files={"file": ("한글 파일.txt", data)})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get("/files").json()["files"],
                         [{"filename": "한글 파일.txt", "size": len(data)}])
        response = self.client.get("/download", params={"filename": "한글 파일.txt"})
        self.assertEqual(response.content, data)
        self.assertIn("attachment", response.headers["content-disposition"])

    def test_duplicate_preserves_original(self):
        self.client.post("/upload", files={"file": ("test.txt", b"first")})
        response = self.client.post("/upload", files={"file": ("test.txt", b"second")})
        self.assertEqual(response.status_code, 409)
        self.assertEqual((self.directory / "test.txt").read_bytes(), b"first")
        self.assertEqual(len(list(self.directory.iterdir())), 1)

    def test_invalid_names(self):
        for name in ["../secret.txt", "..\\secret.txt", ".env", "a:b", "NUL.txt"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get("/download", params={"filename": name}).status_code, 400)
                self.assertEqual(self.client.post("/upload", files={"file": (name, b"x")}).status_code, 400)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_missing_file_and_required_parameters(self):
        self.assertEqual(self.client.get("/download", params={"filename": "missing.txt"}).status_code, 404)
        self.assertEqual(self.client.get("/download").status_code, 422)
        self.assertEqual(self.client.post("/upload").status_code, 422)

    def test_size_limit_cleans_up(self):
        with patch.object(main, "MAX_FILE_SIZE", 3):
            self.assertEqual(self.client.post("/upload", files={"file": ("big.txt", b"1234")}).status_code, 413)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_symlinks_are_hidden_and_rejected(self):
        (self.directory / "alias.txt").symlink_to(Path(main.__file__))
        self.assertEqual(self.client.get("/files").json()["count"], 0)
        self.assertEqual(self.client.get("/download", params={"filename": "alias.txt"}).status_code, 400)

    def test_docs_and_schema(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(set(schema["paths"]), {"/upload", "/download", "/files"})
        self.assertIn("multipart/form-data", schema["paths"]["/upload"]["post"]["requestBody"]["content"])


if __name__ == "__main__":
    unittest.main()
