"""/auth — 가입, 로그인, 디바이스 등록/제거."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session  # noqa

from config import settings
from db import get_db
from deps import current_user
from models import User, Device
from security import (
    create_access_token, generate_license_key, hash_password, verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == req.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 이메일")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        license_key=generate_license_key(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.license_key)
    return AuthResponse(access_token=token, license_key=user.license_key,
                        user_id=user.id)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == req.email))
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일/비밀번호 불일치")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "계정 비활성")

    # 디바이스 등록/검증 — 라이선스 1인 N대 정책
    device = db.scalar(
        select(Device).where(Device.user_id == user.id, Device.hwid == req.hwid)
    )
    if device:
        device.hostname = req.hostname or device.hostname
    else:
        active_count = db.query(Device).filter(Device.user_id == user.id).count()
        if active_count >= settings.DEVICES_PER_USER:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"라이선스 디바이스 한도 초과 ({settings.DEVICES_PER_USER}대). "
                f"기존 디바이스를 해제하세요."
            )
        device = Device(user_id=user.id, hwid=req.hwid, hostname=req.hostname)
        db.add(device)
    db.commit()

    token = create_access_token(user.id, user.license_key)
    return AuthResponse(access_token=token, license_key=user.license_key,
                        user_id=user.id)


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
