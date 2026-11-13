"""API 입력·출력 형식."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]


class UserCreate(BaseModel):
    name: Name = Field(examples=["김유신"])
    email: Email = Field(examples=["yusin@example.com"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    created_at: datetime


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    size: int
    user_id: int
    created_at: datetime


class FileList(BaseModel):
    count: int
    files: list[FileRead]
    unregistered_files: list[str] = Field(
        description="static/files에는 있지만 DB 정보가 없는 파일(예전에 올린 파일 등)"
    )
