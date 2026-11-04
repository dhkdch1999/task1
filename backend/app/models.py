"""API 요청·응답 스키마."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Cycle = Literal["매일", "매주", "매월", "분기", "비정기"]
Status = Literal["정기", "진행 중", "완료", "참고"]
SuccessorState = Literal["none", "confirmed", "question"]


class SourceFileIn(BaseModel):
    name: str = Field(max_length=300)
    content: str


class FiltersIn(BaseModel):
    exclude_senders: list[str] = []
    exclude_keywords: list[str] = []
    exclude_folders: list[str] = []


class PreviewIn(BaseModel):
    owner_email: str | None = None
    mails: list[SourceFileIn] = []
    files: list[SourceFileIn] = []


class AnalyzeIn(PreviewIn):
    title: str | None = None
    owner_name: str = Field(min_length=1, max_length=50)
    successor_name: str | None = Field(default=None, max_length=50)
    filters: FiltersIn = FiltersIn()


class Person(BaseModel):
    name: str
    email: str = ""
    org: str | None = None


class CardIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    cycle: Cycle = "비정기"
    status: Status = "정기"
    category: str = "기타"
    related_files: list[str] = []
    related_people: list[Person] = []
    caution: str = ""


class CardPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    cycle: Cycle | None = None
    status: Status | None = None
    category: str | None = None
    related_files: list[str] | None = None
    related_people: list[Person] | None = None
    caution: str | None = None


class MergeIn(BaseModel):
    card_ids: list[int] = Field(min_length=2)
    title: str | None = None


class ReorderIn(BaseModel):
    card_ids: list[int]


class CheckIn(BaseModel):
    state: SuccessorState


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
