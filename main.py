"""수업 과제: /docs에서 테스트하는 파일 업로드·다운로드·목록 API."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "static" / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MiB

app = FastAPI(title="김유신 FastAPI 파일 관리", version="1.0.0")


def file_path(filename: str) -> Path:
    """파일명만 허용하여 저장 폴더 밖으로 접근하는 것을 차단한다."""
    if (
        not filename or filename.startswith(".")
        or filename.endswith((".", " "))
        or any(char in filename for char in '/\\:*?"<>|')
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
        or len(filename.encode("utf-8")) > 240
        or filename.split(".")[0].upper() in {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
    ):
        raise HTTPException(400, "경로 없이 올바른 파일명만 입력해주세요.")
    path = FILES_DIR / filename
    if path.is_symlink():
        raise HTTPException(400, "심볼릭 링크는 사용할 수 없습니다.")
    return path


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/docs")


@app.post("/upload", status_code=201, tags=["파일 관리"], summary="파일 업로드")
def upload_file(file: Annotated[UploadFile, File(description="최대 20 MiB 파일")]):
    """선택한 파일을 프로젝트의 static/files에 저장합니다. 중복 이름은 409입니다."""
    temporary_path = None
    try:
        target = file_path(file.filename or "")
        size = 0
        # 전송 중인 파일은 목록에 노출하지 않는다.
        with NamedTemporaryFile(dir=FILES_DIR, prefix=".upload-", delete=False) as output:
            temporary_path = Path(output.name)
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(413, "파일 크기는 20 MiB 이하여야 합니다.")
                output.write(chunk)
        try:
            # 완성된 파일만 공개하고, 같은 이름이 있으면 덮어쓰지 않는다.
            os.link(temporary_path, target)
        except FileExistsError:
            raise HTTPException(409, "같은 이름의 파일이 있습니다. 이름을 바꿔주세요.")
        return {"filename": target.name, "size": size, "message": "업로드 완료"}
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        file.file.close()


@app.get("/download", response_class=FileResponse, tags=["파일 관리"], summary="파일 다운로드")
def download_file(filename: Annotated[str, Query(description="확장자를 포함한 파일명")]):
    """파일명을 입력하면 해당 파일을 다운로드합니다."""
    path = file_path(filename)
    if not path.is_file():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/files", tags=["파일 관리"], summary="전체 파일 목록 조회")
def list_files():
    files = [
        {"filename": path.name, "size": path.stat().st_size}
        for path in sorted(FILES_DIR.iterdir())
        if not path.name.startswith(".") and not path.is_symlink() and path.is_file()
    ]
    return {"count": len(files), "files": files}
