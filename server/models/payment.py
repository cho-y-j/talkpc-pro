"""Payment — 결제 이력 (포트원).

각 결제 건의 진위는 PortOne API 로 verify 후 기록.
정기결제(빌링키) 는 PortOne 측에서 자동 결제 → webhook 으로 통보.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from db import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36),
                                          ForeignKey("users.id", ondelete="CASCADE"),
                                          index=True)
    # PortOne 결제 ID (paymentId / billingKey)
    portone_payment_id: Mapped[str] = mapped_column(String(64), unique=True,
                                                      index=True)
    plan: Mapped[str] = mapped_column(String(32), default="monthly")  # monthly | yearly
    amount: Mapped[int] = mapped_column(Integer, default=0)  # 원화
    currency: Mapped[str] = mapped_column(String(8), default="KRW")
    status: Mapped[str] = mapped_column(String(16), default="paid", index=True)
    # paid | failed | cancelled | refunded
    method: Mapped[str] = mapped_column(String(32), default="")  # card / kakaopay / ...
    receipt_url: Mapped[str] = mapped_column(Text, default="")
    raw_response: Mapped[str] = mapped_column(Text, default="")  # 디버그용
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
