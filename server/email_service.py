"""이메일 발송 — Resend.com.

ENV:
  RESEND_API_KEY        Resend API 키
  RESEND_FROM           발신 이메일 (예: 'TalkPC Pro <no-reply@talkpc-pro.com>')

미설정 시 무시 (silent skip) — 개발 단계 friction 최소화.
"""
import os
from typing import Optional

import httpx

RESEND_API_BASE = "https://api.resend.com"


def _enabled() -> bool:
    return bool(os.environ.get("RESEND_API_KEY")
                and os.environ.get("RESEND_FROM"))


def send_email(to: str, subject: str, html: str,
                text: Optional[str] = None) -> bool:
    """이메일 발송 — 실패해도 예외 안 던짐 (best-effort)."""
    if not _enabled():
        return False
    try:
        r = httpx.post(
            f"{RESEND_API_BASE}/emails",
            headers={
                "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={
                "from": os.environ["RESEND_FROM"],
                "to": [to],
                "subject": subject,
                "html": html,
                **({"text": text} if text else {}),
            },
            timeout=10.0,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False


# ── 템플릿 ──

BRAND = "TalkPC Pro"
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@talkpc-pro.com")


def _wrap(body_html: str, title: str = "") -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;color:#111;
max-width:560px;margin:0 auto;padding:32px 24px;">
  <h1 style="font-size:24px;font-weight:700;margin:0 0 16px;color:#0f172a;">
    {title or BRAND}
  </h1>
  {body_html}
  <hr style="margin:32px 0;border:0;border-top:1px solid #e2e8f0;">
  <p style="font-size:12px;color:#64748b;">
    문의: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a><br>
    이 메일은 자동 발송되었습니다.
  </p>
</body></html>"""


def email_signup_welcome(to: str, license_key: str):
    html = _wrap(f"""
        <p>{BRAND} 가입을 환영합니다!</p>
        <p>회원님의 가입은 <b>관리자 승인 대기 중</b>입니다.
           승인 후 다시 안내드리겠습니다.</p>
        <p>임시 라이선스 키:<br>
        <code style="background:#f1f5f9;padding:6px 10px;
                       border-radius:6px;font-family:ui-monospace;">
        {license_key}</code></p>
    """, title="가입 환영")
    return send_email(to, f"[{BRAND}] 가입 완료 — 승인 대기", html)


def email_approved(to: str):
    html = _wrap(f"""
        <p>회원님의 계정이 <b>승인되었습니다</b>.</p>
        <p>앱에서 로그인하시면 바로 사용하실 수 있습니다.</p>
    """, title="가입 승인")
    return send_email(to, f"[{BRAND}] 계정이 승인되었습니다", html)


def email_payment_receipt(to: str, plan: str, amount: int,
                             receipt_url: str, expires_at):
    plan_label = "월간" if plan == "monthly" else "연간"
    html = _wrap(f"""
        <p>결제가 완료되었습니다.</p>
        <ul>
          <li>요금제: <b>{plan_label} 구독</b></li>
          <li>금액: <b>{amount:,}원</b></li>
          <li>다음 만료일: <b>{expires_at}</b></li>
        </ul>
        {f'<p><a href="{receipt_url}">영수증 보기</a></p>' if receipt_url else ''}
        <p>이용해주셔서 감사합니다.</p>
    """, title="결제 완료")
    return send_email(to, f"[{BRAND}] 결제 영수증", html)


def email_expiry_warning(to: str, days_left: int, expires_at):
    html = _wrap(f"""
        <p>구독 만료가 <b>{days_left}일</b> 남았습니다.</p>
        <p>만료일: <b>{expires_at}</b></p>
        <p>중단 없이 이용하시려면 앱에서 결제 갱신해주세요.</p>
    """, title="구독 만료 임박")
    return send_email(to, f"[{BRAND}] 구독이 {days_left}일 후 만료됩니다", html)


def email_suspended(to: str, reason: str = ""):
    html = _wrap(f"""
        <p>회원님의 계정이 <b>일시 정지</b>되었습니다.</p>
        {f'<p>사유: {reason}</p>' if reason else ''}
        <p>문의가 있으시면 {SUPPORT_EMAIL} 로 연락해주세요.</p>
    """, title="계정 정지 안내")
    return send_email(to, f"[{BRAND}] 계정 정지 안내", html)
