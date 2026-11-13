"""MySQL 연결 설정. 접속 정보는 환경변수 또는 프로젝트 폴더의 .env에서 읽는다."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def mysql_url(database: str | None = None) -> URL:
    """URL.create는 비밀번호의 특수문자(@, :, / 등)를 안전하게 처리한다."""
    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "fastapi_user"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=database or os.getenv("DB_NAME", "fastapi_db"),
        query={"charset": "utf8mb4"},
    )


def make_engine(database: str | None = None):
    return create_engine(mysql_url(database), pool_pre_ping=True, pool_recycle=3600)


class Base(DeclarativeBase):
    pass


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
