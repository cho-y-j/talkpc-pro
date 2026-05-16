"""Template — 메시지 템플릿 (변형 contents JSON 보관)."""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from db import Base


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36),
                                          ForeignKey("users.id", ondelete="CASCADE"),
                                          index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    contents: Mapped[list] = mapped_column(JSON, default=list)  # 변형 리스트
    category: Mapped[str] = mapped_column(String(32), default="all")
    image_path: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                   onupdate=datetime.utcnow,
                                                   index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
