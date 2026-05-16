"""/logs/* — 발송 로그 + 일일 한도 + 부정 사용 감지."""
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session  # noqa

from db import get_db
from deps import current_user, admin_user
from models import User, SendLog
from models.user import USER_STATUS_ACTIVE

router = APIRouter(prefix="/logs", tags=["logs"])

# 환경변수로 조정 가능한 정책
DAILY_LIMIT = int(os.environ.get("DAILY_SEND_LIMIT", "300"))
ABUSE_THRESHOLD = int(os.environ.get("ABUSE_DAILY_THRESHOLD", "500"))


class SendLogCreate(BaseModel):
    contact_name: str = ""
    channel: str = "kakao_bot"  # kakao_bot | alimtalk | sms
    status: str = "success"
    message_preview: str = ""
    detail: str = ""


class SendLogRow(BaseModel):
    id: str
    contact_name: str
    channel: str
    status: str
    message_preview: str
    detail: str
    sent_at: datetime


class SendLogListResponse(BaseModel):
    total: int
    today_count: int
    daily_limit: int
    logs: list[SendLogRow]


@router.post("", response_model=dict)
def create_log(req: SendLogCreate, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """클라가 발송 결과를 서버에 audit 로그로 기록.

    동시에 일일 한도 체크 — 초과 시 다음 발송 전 클라가 알 수 있게 메타 반환.
    """
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "계정 비활성")

    # 일일 한도 (오늘 자정 ~ 지금) 계산
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0,
                                              microsecond=0)
    today_count = db.scalar(
        select(func.count(SendLog.id))
        .where(SendLog.user_id == user.id, SendLog.sent_at >= today_start)
    ) or 0

    # 부정 사용 감지 — 임계치 초과 시 자동 정지 (어드민 검토 필요)
    if today_count >= ABUSE_THRESHOLD:
        from models.user import USER_STATUS_SUSPENDED
        user.status = USER_STATUS_SUSPENDED
        user.status_changed_at = datetime.utcnow()
        user.admin_note = (f"자동 정지 — 일일 {ABUSE_THRESHOLD}건 초과 "
                            f"({today_count}건 발송). 어드민 검토 필요.")
        log = SendLog(user_id=user.id, contact_name=req.contact_name,
                       channel=req.channel, status="auto_suspended",
                       message_preview=req.message_preview[:200],
                       detail="abuse_threshold_exceeded")
        db.add(log)
        db.commit()
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"부정 사용 의심 — 자동 정지 (일일 {today_count}건). "
            f"관리자에게 문의해주세요.",
        )

    # 일일 한도 도달 시 차단
    if today_count >= DAILY_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"일일 발송 한도 도달 ({DAILY_LIMIT}건). 내일 다시 시도하세요.",
        )

    # 정상 기록
    log = SendLog(user_id=user.id, contact_name=req.contact_name,
                   channel=req.channel, status=req.status,
                   message_preview=req.message_preview[:200],
                   detail=req.detail[:1000])
    db.add(log)
    db.commit()
    return {
        "ok": True,
        "today_count": today_count + 1,
        "daily_limit": DAILY_LIMIT,
        "remaining": max(0, DAILY_LIMIT - today_count - 1),
    }


@router.get("", response_model=SendLogListResponse)
def list_logs(limit: int = 100, offset: int = 0,
               user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """사용자 본인의 발송 로그 (최근 → 과거)."""
    total = db.scalar(
        select(func.count(SendLog.id)).where(SendLog.user_id == user.id)
    ) or 0
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0,
                                              microsecond=0)
    today_count = db.scalar(
        select(func.count(SendLog.id))
        .where(SendLog.user_id == user.id, SendLog.sent_at >= today_start)
    ) or 0

    rows = db.scalars(
        select(SendLog).where(SendLog.user_id == user.id)
        .order_by(SendLog.sent_at.desc())
        .limit(limit).offset(offset)
    ).all()

    return SendLogListResponse(
        total=total,
        today_count=today_count,
        daily_limit=DAILY_LIMIT,
        logs=[
            SendLogRow(
                id=r.id, contact_name=r.contact_name, channel=r.channel,
                status=r.status, message_preview=r.message_preview,
                detail=r.detail, sent_at=r.sent_at,
            ) for r in rows
        ],
    )


@router.get("/admin/abuse", response_model=list[dict])
def admin_abuse_detect(days: int = Query(1, ge=1, le=30),
                        threshold: int = Query(100, ge=1),
                        _admin: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    """어드민 — 의심 사용자 목록 (최근 N일 발송 > threshold)."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.execute(
        select(User.email, User.id, User.status,
                func.count(SendLog.id).label("count"))
        .join(SendLog, SendLog.user_id == User.id)
        .where(SendLog.sent_at >= since)
        .group_by(User.id, User.email, User.status)
        .having(func.count(SendLog.id) >= threshold)
        .order_by(func.count(SendLog.id).desc())
    ).all()
    return [
        {
            "user_id": r.id, "email": r.email, "status": r.status,
            "count": r.count, "period_days": days,
        }
        for r in rows
    ]
