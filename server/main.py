"""TalkPC Pro 백엔드 — FastAPI on Vercel + Neon Postgres."""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api import auth, admin, sync, version, logs, billing

# ── Sentry (SENTRY_DSN 설정 시만 활성) ──
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1,
                     profiles_sample_rate=0.0,
                     environment=os.environ.get("SENTRY_ENV", "production"))

# ── Rate limiter (in-memory — serverless 환경에선 인스턴스별 카운트) ──
limiter = Limiter(key_func=get_remote_address, config_filename=None)

app = FastAPI(
    title="TalkPC Pro API",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── CORS ──
# 기본은 모두 허용 (PC 클라 = 별도 origin, 어드민 = web). 환경변수로 좁히기 가능.
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
origins = ["*"] if allowed_origins == "*" else [
    o.strip() for o in allowed_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 라우터 ──
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(sync.router)
app.include_router(version.router)
app.include_router(logs.router)
app.include_router(billing.router)


@app.get("/")
def root():
    return {"service": "talkpc-pro", "status": "ok"}


@app.get("/health")
def health():
    return {"ok": True}


# ── 약관 / 개인정보처리방침 (한국 PIPA 법적 요건) ──

_TERMS_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>이용약관 — TalkPC Pro</title>
<style>body{font-family:-apple-system,sans-serif;max-width:720px;margin:40px auto;
padding:0 24px;color:#1e293b;line-height:1.6}h1{font-size:28px}
h2{font-size:18px;margin-top:32px}p,li{font-size:14px}</style></head>
<body>
<h1>TalkPC Pro 이용약관</h1>
<p><b>시행일:</b> 2026-05-16</p>

<h2>제1조 (목적)</h2>
<p>본 약관은 TalkPC Pro(이하 "서비스")가 제공하는 카카오톡 자동 발송 보조 도구
및 부가 서비스(연락처/템플릿 관리, 알림톡 발송 등)의 이용 조건을 정합니다.</p>

<h2>제2조 (서비스의 내용)</h2>
<ul>
<li>카카오톡 PC 자동 발송 기능</li>
<li>연락처/메시지 템플릿의 클라우드 보관 및 복구</li>
<li>알림톡/SMS 발송 (세종텔레콤 연동, 별도 약관)</li>
<li>발송 이력 통계 및 관리자 대시보드</li>
</ul>

<h2>제3조 (이용자의 의무)</h2>
<ul>
<li>스팸, 사기, 불법 광고 등 위법 목적으로 사용하지 않을 것</li>
<li>수신자의 사전 동의 없이 마케팅 메시지를 발송하지 않을 것 (정보통신망법)</li>
<li>라이선스 키 및 계정 정보를 타인과 공유하지 않을 것</li>
<li>일일 발송 한도 등 서비스가 정한 정책을 준수할 것</li>
</ul>

<h2>제4조 (서비스 제한)</h2>
<p>다음의 경우 운영자는 사전 통지 없이 계정을 정지할 수 있습니다.</p>
<ul>
<li>비정상적 대량 발송 (일일 한도 초과 반복)</li>
<li>다수의 신고가 접수되거나 스팸 의심 행위</li>
<li>본 약관 또는 관련 법령 위반</li>
</ul>

<h2>제5조 (요금 및 환불)</h2>
<p>구독 결제 후 7일 이내 미사용 시 전액 환불 가능합니다.
이후엔 비례 환불 또는 부분 환불 정책에 따릅니다. 자세한 내용은
<a href="mailto:support@talkpc-pro.com">support@talkpc-pro.com</a> 으로 문의하세요.</p>

<h2>제6조 (책임의 한계)</h2>
<p>본 서비스는 카카오톡 PC 클라이언트의 UI 자동화에 의존합니다.
카카오 측 정책 변경 또는 UI 변경으로 발생하는 일시적 장애에 대해
운영자는 가능한 신속히 대응하지만, 발송 실패로 인한 직접적/간접적
손해에 대한 책임은 지지 않습니다.</p>

<h2>제7조 (분쟁 해결)</h2>
<p>본 약관과 관련된 분쟁은 대한민국 법령에 따라 해결합니다.
관할 법원은 운영자 소재지 관할 법원으로 합니다.</p>

<p style="margin-top:48px;color:#64748b;font-size:12px;">
<a href="/privacy">개인정보처리방침</a> ·
<a href="mailto:support@talkpc-pro.com">문의</a>
</p></body></html>
"""

_PRIVACY_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>개인정보처리방침 — TalkPC Pro</title>
<style>body{font-family:-apple-system,sans-serif;max-width:720px;margin:40px auto;
padding:0 24px;color:#1e293b;line-height:1.6}h1{font-size:28px}
h2{font-size:18px;margin-top:32px}p,li{font-size:14px}</style></head>
<body>
<h1>TalkPC Pro 개인정보처리방침</h1>
<p><b>시행일:</b> 2026-05-16</p>

<h2>1. 수집하는 개인정보</h2>
<ul>
<li><b>가입 시:</b> 이메일 주소, 비밀번호(bcrypt 해시 저장)</li>
<li><b>이용 시:</b> 디바이스 식별자(HWID, 해시값), 호스트명, 접속 IP</li>
<li><b>발송 시:</b> 연락처 정보(이름, 전화번호, 회사 등 — 사용자가 직접 등록한 것),
   메시지 템플릿, 발송 이력 (수신자명, 결과, 시각)</li>
<li><b>결제 시:</b> 결제수단 정보는 포트원(PG)에서 처리, 본 서비스는 결제ID와 영수증만 보관</li>
</ul>

<h2>2. 수집 목적</h2>
<ul>
<li>회원 식별 및 인증, 라이선스 검증</li>
<li>서비스 제공 (연락처/템플릿 클라우드 백업, 재설치 후 복구)</li>
<li>부정 사용 방지 (일일 한도 초과, 스팸 의심)</li>
<li>고객 지원 및 문의 응대</li>
<li>법령상 의무 이행 (전자상거래법, 통신비밀보호법)</li>
</ul>

<h2>3. 보유 기간</h2>
<ul>
<li>회원 정보: 회원 탈퇴 시 즉시 파기 (단, 관련 법령상 보존 의무 기간 제외)</li>
<li>결제 기록: 5년 (전자상거래법)</li>
<li>발송 로그: 1년 (분쟁 대응 목적)</li>
<li>접속 로그: 3개월 (통신비밀보호법)</li>
</ul>

<h2>4. 제3자 제공</h2>
<p>다음의 경우 외에는 이용자의 개인정보를 제3자에게 제공하지 않습니다.</p>
<ul>
<li>이용자의 사전 동의가 있는 경우</li>
<li>법령 또는 수사기관 요청 (영장 등)</li>
</ul>

<h2>5. 처리 위탁</h2>
<ul>
<li><b>Neon (PostgreSQL)</b> — 데이터베이스 호스팅 (AWS 싱가포르 리전)</li>
<li><b>Vercel</b> — API 호스팅</li>
<li><b>포트원</b> — 결제 처리</li>
<li><b>Resend</b> — 이메일 발송</li>
<li><b>Sentry</b> — 에러 모니터링 (사용 시)</li>
</ul>

<h2>6. 이용자의 권리</h2>
<p>이용자는 언제든지 본인의 개인정보 열람, 수정, 삭제, 처리 정지를 요청할 수 있습니다.
<a href="mailto:support@talkpc-pro.com">support@talkpc-pro.com</a> 으로 요청해주세요.</p>

<h2>7. 보안 조치</h2>
<ul>
<li>비밀번호 bcrypt 단방향 해시 저장</li>
<li>HTTPS 통신 강제</li>
<li>JWT 24시간 유효 + 디바이스 묶기</li>
<li>접근 권한 최소화 (어드민 분리)</li>
</ul>

<h2>8. 책임자</h2>
<p>개인정보 보호 책임자: 운영자<br>
연락처: <a href="mailto:support@talkpc-pro.com">support@talkpc-pro.com</a></p>

<p style="margin-top:48px;color:#64748b;font-size:12px;">
<a href="/terms">이용약관</a>
</p></body></html>
"""


@app.get("/terms", response_class=HTMLResponse)
def terms_page():
    return _TERMS_HTML


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page():
    return _PRIVACY_HTML


# Vercel Python runtime 은 모듈 레벨 `app` (ASGI) 자동 감지.
# Mangum 은 AWS Lambda 전용이라 제거 — Vercel 에선 ASGI app 그대로 사용.
