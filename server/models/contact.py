"""Contact — 사용자별 연락처 (서버 보관 → 재설치 후 복구)."""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from db import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36),
                                          ForeignKey("users.id", ondelete="CASCADE"),
                                          index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), default="")
    company: Mapped[str] = mapped_column(String(128), default="")
    position: Mapped[str] = mapped_column(String(64), default="")
    category: Mapped[str] = mapped_column(String(32), default="friend",
                                            index=True)
    birthday: Mapped[str] = mapped_column(String(10), default="")
    anniversary: Mapped[str] = mapped_column(String(10), default="")
    memo: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="")  # CSV
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                   onupdate=datetime.utcnow,
                                                   index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
