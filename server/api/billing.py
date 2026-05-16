"""/billing/* — 포트원 V2 결제 통합.

흐름:
  1. 클라가 포트원 SDK 로 결제 → paymentId 받음
  2. 클라가 server /billing/verify (paymentId) 호출
  3. server 가 포트원 API 로 진위 확인 → DB 기록 + user.expires_at 갱신
     status=active 로 자동 전환

ENV:
  PORTONE_API_SECRET    포트원 V2 API Secret
  PORTONE_STORE_ID      Store ID
  PORTONE_WEBHOOK_SECRET  Webhook 서명 검증용 (선택)

요금제 (서버 측 진실):
  monthly: 19,900원 / 30일
  yearly:  199,000원 / 365일

NOTE: 포트원 미가입/미설정 시에도 import 에러 없이 동작 (verify 호출 시 503).
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session  # noqa

import httpx

from db import get_db
from deps import current_user, admin_user
from models import User, Payment
from models.user import USER_STATUS_ACTIVE

router = APIRouter(prefix="/billing", tags=["billing"])


# ── 요금제 ──

PLANS = {
    "monthly": {"amount": 19900, "days": 30, "label": "월간 구독"},
    "yearly": {"amount": 199000, "days": 365, "label": "연간 구독"},
}


PORTONE_API_SECRET = os.environ.get("PORTONE_API_SECRET", "")
PORTONE_STORE_ID = os.environ.get("PORTONE_STORE_ID", "")
PORTONE_API_BASE = "https://api.portone.io"


def _portone_enabled() -> bool:
    return bool(PORTONE_API_SECRET and PORTONE_STORE_ID)


# ── 스키마 ──

class CheckoutInfo(BaseModel):
    """클라가 결제 시작 전 받아갈 정보."""
    store_id: str
    plan: str
    plan_label: str
    amount: int
    currency: str = "KRW"
    order_name: str
    customer_email: str


class VerifyRequest(BaseModel):
    payment_id: str  # 포트원 SDK 가 반환한 paymentId
    plan: str        # monthly | yearly (서버 측에서 amount 재검증)


class VerifyResponse(BaseModel):
    ok: bool
    new_expires_at: Optional[datetime] = None
    receipt_url: str = ""


class BillingHistoryRow(BaseModel):
    id: str
    plan: str
    amount: int
    status: str
    method: str
    paid_at: Optional[datetime]
    receipt_url: str


# ── 엔드포인트 ──

@router.get("/plans")
def list_plans():
    return {"plans": PLANS, "currency": "KRW", "enabled": _portone_enabled()}


@router.get("/checkout-info", response_model=CheckoutInfo)
def checkout_info(plan: str, user: User = Depends(current_user)):
    """클라가 포트원 SDK 호출 직전 받아갈 메타 — Store ID 가 노출되지만 secret 은 아님."""
    if plan not in PLANS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"잘못된 plan: {plan}")
    if not _portone_enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "결제 시스템 준비중입니다.",
        )
    p = PLANS[plan]
    return CheckoutInfo(
        store_id=PORTONE_STORE_ID,
        plan=plan, plan_label=p["label"],
        amount=p["amount"],
        order_name=f"TalkPC Pro {p['label']}",
        customer_email=user.email,
    )


def _grant_subscription(db: Session, user: User, plan: str,
                         payment: Payment) -> datetime:
    """결제 verify 후 사용자에게 구독 권한 부여."""
    days = PLANS[plan]["days"]
    now = datetime.utcnow()
    # expires_at 이 미래면 거기에 days 추가 (재구독), 과거/없음이면 now + days
    base = (user.expires_at if user.expires_at and user.expires_at > now
            else now)
    user.expires_at = base + timedelta(days=days)
    user.status = USER_STATUS_ACTIVE
    user.status_changed_at = now
    db.commit()
    return user.expires_at


@router.post("/verify", response_model=VerifyResponse)
def verify_payment(req: VerifyRequest, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """클라가 결제 직후 호출 — 포트원 API 로 진위 확인."""
    if not _portone_enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "결제 시스템 준비중입니다.",
        )
    if req.plan not in PLANS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "잘못된 plan")

    # 중복 처리 방지
    dup = db.scalar(select(Payment).where(
        Payment.portone_payment_id == req.payment_id
    ))
    if dup and dup.status == "paid":
        return VerifyResponse(
            ok=True, new_expires_at=user.expires_at,
            receipt_url=dup.receipt_url,
        )

    # 포트원 V2 API 로 결제 조회
    try:
        r = httpx.get(
            f"{PORTONE_API_BASE}/payments/{req.payment_id}",
            headers={"Authorization": f"PortOne {PORTONE_API_SECRET}"},
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                              f"포트원 조회 실패: {e}")

    if data.get("status") != "PAID":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                              f"결제 미완료 상태: {data.get('status')}")
    expected_amount = PLANS[req.plan]["amount"]
    paid_amount = (data.get("amount") or {}).get("total")
    if paid_amount != expected_amount:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"결제 금액 불일치: 기대 {expected_amount}, 실제 {paid_amount}",
        )

    # 결제 기록 + 구독 권한 부여
    pay = Payment(
        user_id=user.id,
        portone_payment_id=req.payment_id,
        plan=req.plan,
        amount=paid_amount,
        currency=data.get("currency", "KRW"),
        status="paid",
        method=(data.get("method") or {}).get("type", ""),
        receipt_url=data.get("receiptUrl", ""),
        raw_response=str(data)[:5000],
        paid_at=datetime.utcnow(),
    )
    db.add(pay)
    new_exp = _grant_subscription(db, user, req.plan, pay)
    return VerifyResponse(ok=True, new_expires_at=new_exp,
                            receipt_url=pay.receipt_url)


@router.post("/webhook")
async def portone_webhook(request: Request, db: Session = Depends(get_db)):
    """포트원 webhook — 정기결제 자동 갱신 등.

    Headers:
      portone-webhook-signature (HMAC-SHA256 of body with WEBHOOK_SECRET)
    """
    body = await request.body()
    payload = await request.json()

    # 서명 검증 (선택 — 환경변수 있을 때만)
    webhook_secret = os.environ.get("PORTONE_WEBHOOK_SECRET", "")
    if webhook_secret:
        import hmac
        import hashlib
        signature = request.headers.get("portone-webhook-signature", "")
        expected = hmac.new(webhook_secret.encode(), body,
                              hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                  "잘못된 서명")

    event_type = payload.get("type", "")
    payment_id = payload.get("data", {}).get("paymentId", "")

    if event_type == "Transaction.Paid" and payment_id:
        # 자동 결제 성공 → 사용자 찾아 구독 연장
        pay = db.scalar(select(Payment).where(
            Payment.portone_payment_id == payment_id
        ))
        if pay:
            return {"ok": True, "duplicate": True}
        # custom data 에서 user_id/plan 추출 (clientside 결제 시 함께 전송)
        custom = payload.get("data", {}).get("customData", {}) or {}
        user_id = custom.get("user_id")
        plan = custom.get("plan", "monthly")
        if not user_id or plan not in PLANS:
            return {"ok": False, "reason": "missing custom data"}
        user = db.get(User, user_id)
        if not user:
            return {"ok": False, "reason": "user not found"}
        amount = (payload.get("data", {}).get("amount") or {}).get("total", 0)
        pay = Payment(
            user_id=user.id, portone_payment_id=payment_id,
            plan=plan, amount=amount, currency="KRW", status="paid",
            method=str(payload.get("data", {}).get("method", "")),
            receipt_url=payload.get("data", {}).get("receiptUrl", ""),
            raw_response=str(payload)[:5000],
            paid_at=datetime.utcnow(),
        )
        db.add(pay)
        _grant_subscription(db, user, plan, pay)
        return {"ok": True}

    return {"ok": True, "ignored": event_type}


@router.get("/history", response_model=list[BillingHistoryRow])
def my_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Payment).where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
    ).all()
    return [
        BillingHistoryRow(
            id=r.id, plan=r.plan, amount=r.amount, status=r.status,
            method=r.method, paid_at=r.paid_at, receipt_url=r.receipt_url,
        ) for r in rows
    ]


# ── 어드민용: 수동으로 구독 부여 (포트원 미가입 기간 동안) ──

class ManualGrantRequest(BaseModel):
    user_id: str
    plan: str
    note: str = ""


@router.post("/admin/manual-grant")
def manual_grant(req: ManualGrantRequest, _admin: User = Depends(admin_user),
                  db: Session = Depends(get_db)):
    """어드민이 결제 없이 구독 부여 (송금 확인 후 수동 활성화)."""
    if req.plan not in PLANS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "잘못된 plan")
    user = db.get(User, req.user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자 없음")

    from uuid import uuid4
    pay = Payment(
        user_id=user.id,
        portone_payment_id=f"manual-{uuid4().hex[:16]}",
        plan=req.plan, amount=0, status="paid",
        method="manual_grant",
        raw_response=req.note,
        paid_at=datetime.utcnow(),
    )
    db.add(pay)
    if req.note:
        user.admin_note = req.note
    new_exp = _grant_subscription(db, user, req.plan, pay)
    return {"ok": True, "new_expires_at": new_exp.isoformat()}
