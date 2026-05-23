"""/auth — 가입, 로그인, heartbeat, 디바이스 관리."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session  # noqa
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings
from db import get_db
from deps import current_user
from models import User, Device
from models.user import (
    USER_STATUS_PENDING, USER_STATUS_ACTIVE, USER_STATUS_EXPIRED,
    USER_STATUS_SUSPENDED, USER_STATUS_REJECTED,
)
from security import (
    create_access_token, generate_license_key, hash_password, verify_password,
)
from email_service import email_signup_welcome

router = APIRouter(prefix="/auth", tags=["auth"])
# slowapi 가 시작 시 cwd 의 .env 를 starlette.Config 로 읽으려다 cp949 충돌 →
# config_filename=None 으로 우회 (환경변수는 OS env 에서 직접 읽음).
limiter = Limiter(key_func=get_remote_address, config_filename=None)


# ── 요청/응답 스키마 ──

class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    hwid: str
    hostname: str = ""


class AuthResponse(BaseModel):
    access_token: str | None = None  # status=active 일 때만 발급
    license_key: str
    user_id: str
    status: str
    status_message: str = ""  # 사용자에게 보일 안내 문구
    expires_at: datetime | None = None


class HeartbeatRequest(BaseModel):
    hwid: str


# ── 헬퍼 ──

_STATUS_MESSAGES = {
    USER_STATUS_PENDING: "관리자 승인 대기 중입니다. 승인 후 다시 로그인해주세요.",
    USER_STATUS_ACTIVE: "정상",
    USER_STATUS_EXPIRED: "구독이 만료되었습니다. 결제 후 다시 이용해주세요.",
    USER_STATUS_SUSPENDED: "계정이 일시 정지되었습니다. 관리자에게 문의해주세요.",
    USER_STATUS_REJECTED: "가입이 거부되었습니다.",
}


def _build_auth_response(user: User, with_token: bool) -> AuthResponse:
    token = None
    if with_token and user.status == USER_STATUS_ACTIVE:
        token = create_access_token(user.id, user.license_key)
    return AuthResponse(
        access_token=token,
        license_key=user.license_key,
        user_id=user.id,
        status=user.status,
        status_message=_STATUS_MESSAGES.get(user.status, ""),
        expires_at=user.expires_at,
    )


# ── 엔드포인트 ──

@router.post("/signup", response_model=AuthResponse)
@limiter.limit("5/hour")
def signup(request: Request, req: SignupRequest, db: Session = Depends(get_db)):
    """셀프 가입 — 상태는 pending. 어드민 승인 후 로그인 가능."""
    if db.scalar(select(User).where(User.email == req.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 이메일")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        license_key=generate_license_key(),
        status=USER_STATUS_PENDING,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # 환영 이메일 (Resend 미설정 시 silent skip)
    email_signup_welcome(user.email, user.license_key)
    # 토큰 발급 안 함 — pending 이라 로그인 차단
    return _build_auth_response(user, with_token=False)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == req.email))
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일/비밀번호 불일치")

    # 상태 검증 — active 외엔 차단 (안내 메시지와 함께)
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            _STATUS_MESSAGES.get(user.status, "계정을 사용할 수 없습니다."),
        )

    # 구독 만료 체크
    if user.expires_at and user.expires_at < datetime.utcnow():
        user.status = USER_STATUS_EXPIRED
        user.status_changed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                              _STATUS_MESSAGES[USER_STATUS_EXPIRED])

    # 디바이스 등록/검증
    device = db.scalar(
        select(Device).where(Device.user_id == user.id, Device.hwid == req.hwid)
    )
    if device:
        device.hostname = req.hostname or device.hostname
        device.last_seen = datetime.utcnow()
    else:
        active_count = db.query(Device).filter(Device.user_id == user.id).count()
        limit = user.device_limit if user.device_limit is not None else settings.DEVICES_PER_USER
        if active_count >= limit:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"라이선스 디바이스 한도 초과 ({limit}대). "
                f"기존 디바이스를 해제하세요.",
            )
        device = Device(user_id=user.id, hwid=req.hwid, hostname=req.hostname)
        db.add(device)

    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _build_auth_response(user, with_token=True)


@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """클라가 3분마다 호출 — 상태 변화 즉시 반영 + last_seen 갱신.

    어드민이 suspended/expired 로 바꾸면 다음 heartbeat 에서 클라가
    감지하고 발송 차단.
    """
    # 상태 재검증
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            _STATUS_MESSAGES.get(user.status, "계정 비활성"),
        )
    if user.expires_at and user.expires_at < datetime.utcnow():
        user.status = USER_STATUS_EXPIRED
        user.status_changed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                              _STATUS_MESSAGES[USER_STATUS_EXPIRED])

    device = db.scalar(
        select(Device).where(Device.user_id == user.id, Device.hwid == req.hwid)
    )
    if device:
        device.last_seen = datetime.utcnow()
        db.commit()

    return {
        "ok": True,
        "status": user.status,
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
    }


# ── 디바이스 관리 ──

class DeviceInfo(BaseModel):
    id: str
    hwid: str
    hostname: str
    last_seen: str


@router.get("/devices", response_model=list[DeviceInfo])
def list_devices(user: User = Depends(current_user), db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.user_id == user.id).all()
    return [
        DeviceInfo(id=d.id, hwid=d.hwid, hostname=d.hostname,
                   last_seen=d.last_seen.isoformat())
        for d in devices
    ]


@router.delete("/devices/{device_id}")
def remove_device(device_id: str, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == user.id
    ).first()
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "디바이스 없음")
    db.delete(device)
    db.commit()
    return {"ok": True}
