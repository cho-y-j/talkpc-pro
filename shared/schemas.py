"""클라이언트-서버 공통 Pydantic 스키마.

서버는 그대로 사용. 클라이언트는 import 또는 형태만 참고.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# ── 인증 ──

class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    hwid: str
    hostname: str = ""


class AuthResponse(BaseModel):
    access_token: str
    license_key: str
    user_id: str


# ── 연락처 ──

class ContactBase(BaseModel):
    name: str
    phone: str = ""
    company: str = ""
    position: str = ""
    category: str = "friend"
    birthday: str = ""
    anniversary: str = ""
    memo: str = ""
    tags: str = ""


class ContactCreate(ContactBase):
    pass


class ContactOut(ContactBase):
    id: str
    updated_at: datetime
    created_at: datetime


# ── 템플릿 ──

class TemplateBase(BaseModel):
    name: str
    contents: list[str] = []
    category: str = "all"
    image_path: str = ""


class TemplateCreate(TemplateBase):
    pass


class TemplateOut(TemplateBase):
    id: str
    updated_at: datetime
    created_at: datetime


# ── 동기화 ──

class SyncPullRequest(BaseModel):
    since: Optional[datetime] = None  # None 이면 전체


class SyncPushRequest(BaseModel):
    contacts: list[ContactCreate] = []
    templates: list[TemplateCreate] = []
