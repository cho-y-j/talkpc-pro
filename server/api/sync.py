"""/sync/* — 연락처/템플릿 양방향 동기화 (LWW).

흐름:
  pull: 클라가 last_sync_at 보내고 그 이후 변경분 받음 (전체 처음엔 None)
  push: 클라가 로컬 변경분 보내고 서버가 upsert (updated_at 비교, server 가 더 새것이면 무시)
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session  # noqa

from db import get_db
from deps import current_user
from models import User, Contact, Template
from models.user import USER_STATUS_ACTIVE

router = APIRouter(prefix="/sync", tags=["sync"])


# ── 활성 사용자만 통과 ──

def _require_active(user: User):
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "계정이 활성 상태가 아닙니다")


# ── 스키마 ──

class ContactDTO(BaseModel):
    id: Optional[str] = None  # None 이면 새로 생성, 있으면 upsert
    name: str
    phone: str = ""
    company: str = ""
    position: str = ""
    category: str = "friend"
    birthday: str = ""
    anniversary: str = ""
    memo: str = ""
    tags: str = ""
    updated_at: Optional[datetime] = None


class TemplateDTO(BaseModel):
    id: Optional[str] = None
    name: str
    contents: list[str] = []
    category: str = "all"
    image_path: str = ""
    updated_at: Optional[datetime] = None


class SyncPullResponse(BaseModel):
    server_time: datetime
    contacts: list[ContactDTO]
    templates: list[TemplateDTO]


class SyncPushRequest(BaseModel):
    contacts: list[ContactDTO] = []
    templates: list[TemplateDTO] = []
    deleted_contact_ids: list[str] = []
    deleted_template_ids: list[str] = []


class SyncPushResponse(BaseModel):
    server_time: datetime
    accepted_contacts: int
    rejected_contacts: int  # LWW 충돌로 거부된 수
    accepted_templates: int
    rejected_templates: int
    deleted: int


# ── pull ──

@router.get("/pull", response_model=SyncPullResponse)
def pull(since: Optional[datetime] = None,
          user: User = Depends(current_user),
          db: Session = Depends(get_db)):
    """클라가 since 이후 변경된 데이터 받기. since=None 이면 전체."""
    _require_active(user)

    contacts_q = select(Contact).where(Contact.user_id == user.id)
    if since:
        contacts_q = contacts_q.where(Contact.updated_at > since)
    contacts = db.scalars(contacts_q.order_by(Contact.updated_at)).all()

    templates_q = select(Template).where(Template.user_id == user.id)
    if since:
        templates_q = templates_q.where(Template.updated_at > since)
    templates = db.scalars(templates_q.order_by(Template.updated_at)).all()

    return SyncPullResponse(
        server_time=datetime.utcnow(),
        contacts=[
            ContactDTO(
                id=c.id, name=c.name, phone=c.phone, company=c.company,
                position=c.position, category=c.category,
                birthday=c.birthday, anniversary=c.anniversary,
                memo=c.memo, tags=c.tags, updated_at=c.updated_at,
            ) for c in contacts
        ],
        templates=[
            TemplateDTO(
                id=t.id, name=t.name, contents=t.contents,
                category=t.category, image_path=t.image_path,
                updated_at=t.updated_at,
            ) for t in templates
        ],
    )


# ── push ──

@router.post("/push", response_model=SyncPushResponse)
def push(req: SyncPushRequest,
          user: User = Depends(current_user),
          db: Session = Depends(get_db)):
    """클라 로컬 변경분 서버에 반영. LWW — server.updated_at > req.updated_at 이면 거부."""
    _require_active(user)

    accepted_c = rejected_c = 0
    accepted_t = rejected_t = 0
    deleted = 0

    # 연락처 upsert
    for dto in req.contacts:
        existing = None
        if dto.id:
            existing = db.scalar(select(Contact).where(
                Contact.id == dto.id, Contact.user_id == user.id
            ))
        if existing:
            # LWW: server 가 더 최신이면 거부
            if (dto.updated_at and existing.updated_at
                    and existing.updated_at > dto.updated_at):
                rejected_c += 1
                continue
            existing.name = dto.name
            existing.phone = dto.phone
            existing.company = dto.company
            existing.position = dto.position
            existing.category = dto.category
            existing.birthday = dto.birthday
            existing.anniversary = dto.anniversary
            existing.memo = dto.memo
            existing.tags = dto.tags
            existing.updated_at = datetime.utcnow()
        else:
            new = Contact(
                id=dto.id,  # 없으면 model default uuid4
                user_id=user.id,
                name=dto.name, phone=dto.phone,
                company=dto.company, position=dto.position,
                category=dto.category,
                birthday=dto.birthday, anniversary=dto.anniversary,
                memo=dto.memo, tags=dto.tags,
            )
            if not new.id:
                from uuid import uuid4
                new.id = str(uuid4())
            db.add(new)
        accepted_c += 1

    # 템플릿 upsert
    for dto in req.templates:
        existing = None
        if dto.id:
            existing = db.scalar(select(Template).where(
                Template.id == dto.id, Template.user_id == user.id
            ))
        if existing:
            if (dto.updated_at and existing.updated_at
                    and existing.updated_at > dto.updated_at):
                rejected_t += 1
                continue
            existing.name = dto.name
            existing.contents = dto.contents
            existing.category = dto.category
            existing.image_path = dto.image_path
            existing.updated_at = datetime.utcnow()
        else:
            new = Template(
                id=dto.id,
                user_id=user.id,
                name=dto.name, contents=dto.contents,
                category=dto.category, image_path=dto.image_path,
            )
            if not new.id:
                from uuid import uuid4
                new.id = str(uuid4())
            db.add(new)
        accepted_t += 1

    # 삭제 — 사용자 소유 검증 후 delete
    for cid in req.deleted_contact_ids:
        c = db.scalar(select(Contact).where(
            Contact.id == cid, Contact.user_id == user.id
        ))
        if c:
            db.delete(c)
            deleted += 1
    for tid in req.deleted_template_ids:
        t = db.scalar(select(Template).where(
            Template.id == tid, Template.user_id == user.id
        ))
        if t:
            db.delete(t)
            deleted += 1

    db.commit()
    return SyncPushResponse(
        server_time=datetime.utcnow(),
        accepted_contacts=accepted_c, rejected_contacts=rejected_c,
        accepted_templates=accepted_t, rejected_templates=rejected_t,
        deleted=deleted,
    )
