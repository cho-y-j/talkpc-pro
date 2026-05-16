"""Device — HWID 별 등록 (라이선스 1인 N대 정책 enforce)."""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from db import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36),
                                          ForeignKey("users.id", ondelete="CASCADE"),
                                          index=True)
    hwid: Mapped[str] = mapped_column(String(128), index=True)
    hostname: Mapped[str] = mapped_column(String(128), default="")
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                  onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
