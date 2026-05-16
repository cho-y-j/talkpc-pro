"""User — 이메일 + 비밀번호 해시 + 라이선스 키 + 상태 머신."""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from db import Base


# 상태 머신 (문자열 enum — Alembic 호환 위해 plain string)
USER_STATUS_PENDING = "pending"        # 가입 후 어드민 승인 대기
USER_STATUS_ACTIVE = "active"          # 사용 가능
USER_STATUS_EXPIRED = "expired"        # 구독 만료 (결제 안 됨)
USER_STATUS_SUSPENDED = "suspended"    # 어드민이 차단 (스팸/악용)
USER_STATUS_REJECTED = "rejected"      # 가입 거부


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True,
                                        nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    license_key: Mapped[str] = mapped_column(String(64), unique=True,
                                              index=True, nullable=False)
    # 상태 머신 — pending(가입직후) / active(승인) / expired(결제만료) /
    # suspended(차단) / rejected(거부). 어드민 또는 결제 webhook 으로 변경.
    status: Mapped[str] = mapped_column(String(16),
                                         default=USER_STATUS_PENDING,
                                         index=True)
    # 구독 만료 시각 (결제 통합 후 사용). None 이면 무기한.
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime,
                                                             nullable=True)
    # 어드민 메모 (승인 사유, 차단 이유 등)
    admin_note: Mapped[str] = mapped_column(String(500), default="")
    # 어드민이 마지막으로 상태 변경한 시각
    status_changed_at: Mapped[datetime] = mapped_column(DateTime,
                                                         default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime,
                                                                nullable=True)

    # 어드민 권한 (별도 admin 페이지 인증용)
    is_admin: Mapped[bool] = mapped_column(default=False)
