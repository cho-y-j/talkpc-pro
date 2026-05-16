"""/admin/* — 어드민 전용 엔드포인트.

인증: deps.admin_user (User.is_admin=True 필요)
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session  # noqa

from db import get_db
from deps import admin_user
from models import User, Device, Contact, Template, SendLog
from models.user import (
    USER_STATUS_PENDING, USER_STATUS_ACTIVE, USER_STATUS_EXPIRED,
    USER_STATUS_SUSPENDED, USER_STATUS_REJECTED,
)
from email_service import email_approved, email_suspended

router = APIRouter(prefix="/admin", tags=["admin"])


# ── 응답 스키마 ──

class UserRow(BaseModel):
    id: str
    email: str
    license_key: str
    status: str
    is_admin: bool
    expires_at: Optional[datetime] = None
    admin_note: str = ""
    last_login_at: Optional[datetime] = None
    status_changed_at: datetime
    created_at: datetime
    device_count: int = 0
    send_count_30d: int = 0


class UsersListResponse(BaseModel):
    total: int
    pending: int
    active: int
    expired: int
    suspended: int
    rejected: int
    users: list[UserRow]


class StatusChangeRequest(BaseModel):
    status: str  # active | suspended | rejected | expired
    note: str = ""
    expires_at: Optional[datetime] = None


class StatsResponse(BaseModel):
    total_users: int
    active_users: int
    pending_users: int
    daily_sends: list[dict]  # [{date, count}]
    top_users: list[dict]    # [{email, count}]
    daily_signups: list[dict]


# ── 사용자 관리 ──

@router.get("/users", response_model=UsersListResponse)
def list_users(
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    """사용자 목록 — 상태 필터 + 이메일 검색."""
    stmt = select(User).order_by(User.created_at.desc())
    if status_filter:
        stmt = stmt.where(User.status == status_filter)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(stmt.limit(limit).offset(offset)).all()

    # 상태별 카운트 (전체 기준 — 필터 무관)
    counts = dict(db.execute(
        select(User.status, func.count(User.id)).group_by(User.status)
    ).all())

    # 디바이스 수 + 최근 30일 발송 수 (각 user 별)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    device_counts = dict(db.execute(
        select(Device.user_id, func.count(Device.id)).group_by(Device.user_id)
    ).all())
    send_counts = dict(db.execute(
        select(SendLog.user_id, func.count(SendLog.id))
        .where(SendLog.sent_at >= thirty_days_ago)
        .group_by(SendLog.user_id)
    ).all())

    rows = [
        UserRow(
            id=u.id, email=u.email, license_key=u.license_key,
            status=u.status, is_admin=u.is_admin,
            expires_at=u.expires_at, admin_note=u.admin_note,
            last_login_at=u.last_login_at,
            status_changed_at=u.status_changed_at,
            created_at=u.created_at,
            device_count=device_counts.get(u.id, 0),
            send_count_30d=send_counts.get(u.id, 0),
        )
        for u in users
    ]
    return UsersListResponse(
        total=total,
        pending=counts.get(USER_STATUS_PENDING, 0),
        active=counts.get(USER_STATUS_ACTIVE, 0),
        expired=counts.get(USER_STATUS_EXPIRED, 0),
        suspended=counts.get(USER_STATUS_SUSPENDED, 0),
        rejected=counts.get(USER_STATUS_REJECTED, 0),
        users=rows,
    )


@router.patch("/users/{user_id}/status")
def change_user_status(
    user_id: str, req: StatusChangeRequest,
    _admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    valid = {USER_STATUS_PENDING, USER_STATUS_ACTIVE, USER_STATUS_EXPIRED,
              USER_STATUS_SUSPENDED, USER_STATUS_REJECTED}
    if req.status not in valid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                              f"잘못된 상태: {req.status}")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자 없음")
    prev_status = user.status
    user.status = req.status
    user.status_changed_at = datetime.utcnow()
    if req.note:
        user.admin_note = req.note
    if req.expires_at is not None:
        user.expires_at = req.expires_at
    db.commit()
    # 상태 전환 이메일 (best-effort)
    if prev_status != req.status:
        if req.status == USER_STATUS_ACTIVE and prev_status == USER_STATUS_PENDING:
            email_approved(user.email)
        elif req.status == USER_STATUS_SUSPENDED:
            email_suspended(user.email, req.note)
    return {"ok": True, "status": user.status}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, _admin: User = Depends(admin_user),
                 db: Session = Depends(get_db)):
    """완전 삭제 — 신중. 관련 디바이스/연락처/템플릿/로그 cascade."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자 없음")
    db.delete(user)
    db.commit()
    return {"ok": True}


# ── 통계 ──

@router.get("/stats", response_model=StatsResponse)
def get_stats(days: int = 30, _admin: User = Depends(admin_user),
               db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)

    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(
        select(func.count(User.id)).where(User.status == USER_STATUS_ACTIVE)
    ) or 0
    pending_users = db.scalar(
        select(func.count(User.id)).where(User.status == USER_STATUS_PENDING)
    ) or 0

    # 일별 발송량
    daily_sends_rows = db.execute(
        select(func.date(SendLog.sent_at).label("d"),
                func.count(SendLog.id).label("c"))
        .where(SendLog.sent_at >= since)
        .group_by("d").order_by("d")
    ).all()
    daily_sends = [{"date": str(r.d), "count": r.c} for r in daily_sends_rows]

    # 발송량 top 5 사용자 (최근 N일)
    top_rows = db.execute(
        select(User.email, func.count(SendLog.id).label("c"))
        .join(SendLog, SendLog.user_id == User.id)
        .where(SendLog.sent_at >= since)
        .group_by(User.email)
        .order_by(func.count(SendLog.id).desc())
        .limit(5)
    ).all()
    top_users = [{"email": r.email, "count": r.c} for r in top_rows]

    # 일별 가입자 수
    signup_rows = db.execute(
        select(func.date(User.created_at).label("d"),
                func.count(User.id).label("c"))
        .where(User.created_at >= since)
        .group_by("d").order_by("d")
    ).all()
    daily_signups = [{"date": str(r.d), "count": r.c} for r in signup_rows]

    return StatsResponse(
        total_users=total_users,
        active_users=active_users,
        pending_users=pending_users,
        daily_sends=daily_sends,
        top_users=top_users,
        daily_signups=daily_signups,
    )
