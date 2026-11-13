"""수업 과제: /docs에서 테스트하는 유저 등록·조회와 파일 업로드·다운로드·목록 API (MySQL 연동)."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from database import get_db
from models import FileRecord, User
from schemas import FileList, FileRead, UserCreate, UserRead

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "static" / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MiB

app = FastAPI(title="김유신 FastAPI 파일 관리", version="2.0.0")
DB = Annotated[Session, Depends(get_db)]


@app.exception_handler(OperationalError)
def database_unavailable(request: Request, exc: OperationalError):
    # 비밀번호 등이 노출되지 않도록 원본 오류 내용은 응답에 넣지 않는다.
    return JSONResponse(
        status_code=503,
        content={"detail": "DB에 연결할 수 없습니다. MySQL 실행 여부와 .env 설정을 확인해주세요."},
    )


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


# ---------------------------------------------------------------- 유저 관리

@app.post("/users", status_code=201, response_model=UserRead, tags=["유저 관리"], summary="유저 등록")
def create_user(user: UserCreate, db: DB):
    """이름과 이메일로 유저를 등록합니다. 이미 등록된 이메일은 409입니다."""
    record = User(name=user.name, email=user.email)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "이미 등록된 이메일입니다.")
    db.refresh(record)
    return record


@app.get("/users", response_model=list[UserRead], tags=["유저 관리"], summary="전체 유저 목록 조회")
def list_users(db: DB):
    return db.scalars(select(User).order_by(User.id)).all()


@app.get("/users/{user_id}", response_model=UserRead, tags=["유저 관리"], summary="유저 상세 조회")
def get_user(user_id: int, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "유저를 찾을 수 없습니다.")
    return user


# ---------------------------------------------------------------- 파일 관리

@app.post("/upload", status_code=201, response_model=FileRead, tags=["파일 관리"], summary="파일 업로드")
def upload_file(
    file: Annotated[UploadFile, File(description="최대 20 MiB 파일")],
    user_id: Annotated[int, Form(description="업로드하는 유저의 id (POST /users로 먼저 등록)")],
    db: DB,
):
    """선택한 파일을 static/files에 저장하고, 파일 정보는 DB에 기록합니다. 중복 이름은 409입니다."""
    temporary_path = None
    try:
        target = file_path(file.filename or "")
        if db.get(User, user_id) is None:
            raise HTTPException(404, "유저를 찾을 수 없습니다. 먼저 POST /users로 등록해주세요.")
        if db.scalar(select(FileRecord.id).where(FileRecord.filename == target.name)) is not None:
            raise HTTPException(409, "같은 이름의 파일이 있습니다. 이름을 바꿔주세요.")

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

        # 여기서부터 target은 이번 요청이 새로 만든 파일이므로, DB 저장 실패 시 지워도 안전하다.
        record = FileRecord(filename=target.name, size=size, user_id=user_id)
        db.add(record)
        try:
            db.commit()
        except BaseException as error:
            db.rollback()
            target.unlink(missing_ok=True)
            if isinstance(error, IntegrityError):
                raise HTTPException(409, "같은 이름의 파일이 있거나 유저 정보가 올바르지 않습니다.")
            raise
        db.refresh(record)
        return record
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


def disk_files() -> list[str]:
    return [
        path.name for path in sorted(FILES_DIR.iterdir())
        if not path.name.startswith(".") and not path.is_symlink() and path.is_file()
    ]


@app.get("/files", response_model=FileList, tags=["파일 관리"], summary="전체 파일 목록 조회")
def list_files(db: DB):
    """DB에 기록된 파일 목록과, 폴더에만 있고 DB 정보가 없는 파일 이름을 함께 보여줍니다."""
    records = db.scalars(select(FileRecord).order_by(FileRecord.id)).all()
    registered = {record.filename.casefold() for record in records}
    unregistered = [name for name in disk_files() if name.casefold() not in registered]
    return {"count": len(records), "files": records, "unregistered_files": unregistered}
