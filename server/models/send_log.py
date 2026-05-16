"""SendLog — 발송 이력 (서버 audit, 통계용)."""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from db import Base


class SendLog(Base):
    __tablename__ = "send_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36),
                                          ForeignKey("users.id", ondelete="CASCADE"),
                                          index=True)
    contact_name: Mapped[str] = mapped_column(String(64), default="")
    channel: Mapped[str] = mapped_column(String(16), default="kakao_bot",
                                           index=True)  # kakao_bot | alimtalk | sms
    status: Mapped[str] = mapped_column(String(16), default="success",
                                          index=True)
    message_preview: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                index=True)
