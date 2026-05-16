# TalkPC Pro — AI 작업 메모

## 비전 한 줄

`talk-local` (오프라인 카톡 자동 발송) 의 상용판 — 로그인/서버 DB/라이선스/알림톡 추가.

## 핵심 아키텍처

```
┌──────────────── 사용자 PC ────────────────┐
│  client/                                  │
│  ├── core/   ← talk-local fork (검증된)   │
│  ├── ui/     ← 로그인 + 발송 UI           │
│  └── auth/   ← HWID + JWT 토큰 + API 클라  │
└──────────────────┬────────────────────────┘
                   │ HTTPS / JWT Bearer
                   ▼
┌──────────────── Vercel ──────────────────┐
│  server/  FastAPI + Mangum                │
│  - /auth   가입/로그인/디바이스 관리        │
│  - /sync   연락처/템플릿 동기화 (예정)      │
└──────────────────┬────────────────────────┘
                   │ asyncpg
                   ▼
┌──────────────── Neon ────────────────────┐
│  PostgreSQL — users, devices, contacts,    │
│  templates, send_logs                      │
└────────────────────────────────────────────┘
```

## 🚫 절대 변경 금지 — talk-local 에서 fork 한 검증된 영역

`client/core/` 의 다음 함수들은 **사용자가 95% 정확도 검증** 한 것:

- `kakao_friends.py`: `_paddle_ocr_row`, `_get_paddle_ocr`, `ensure_ready_state`
- `paddle_ocr_helper.py`: `preprocess_for_paddle`, `recognize_korean_text`, `verify_name_match`
- `kakao_sender.py`: `paste_image` (stealth 모드 + chat_hwnd 활성화), `go_back`

자세한 정책은 `talk-local/CLAUDE.md` 참조. 본 디렉토리는 그 fork 이므로 동일 원칙.

## 결정 사항 (확정)

| 항목 | 값 |
|---|---|
| 백엔드 호스팅 | Vercel (Python serverless via Mangum) |
| DB | Neon PostgreSQL (`ap-southeast-1`) |
| 인증 | 이메일+비번 (JWT) + 라이선스 키 |
| 디바이스 정책 | 1인 1대 (HWID 묶기), 환경변수 `DEVICES_PER_USER` 로 조정 |
| ORM | SQLAlchemy 2.x + Alembic |
| 알림톡 | 세종텔레콤 (기존 `core/sejong_sender.py` 확장) |

## 디렉토리

```
talkpc-pro/
├── client/
│   ├── core/             # talk-local core fork (변경 금지 원칙)
│   ├── ui/
│   │   └── login_page.py # 로그인 화면
│   ├── auth/
│   │   ├── api_client.py # 서버 HTTP 클라
│   │   ├── session.py    # %APPDATA%/talkpc-pro/session.json
│   │   └── hwid.py       # MachineGuid + 마더보드 시리얼 해시
│   ├── main.py
│   └── requirements.txt
│
├── server/
│   ├── main.py           # FastAPI app + Mangum handler
│   ├── config.py         # .env 로딩
│   ├── db.py             # SQLAlchemy 엔진/세션
│   ├── security.py       # 비번 해시, JWT, 라이선스 키
│   ├── deps.py           # current_user 의존성
│   ├── api/auth.py       # /auth/* 엔드포인트
│   ├── models/           # ORM 모델
│   ├── migrations/       # Alembic
│   ├── vercel.json
│   ├── requirements.txt
│   └── .env.example
│
├── shared/schemas.py     # Pydantic 공통 스키마
└── docs/
```

## 셋업 절차

### 1. Neon DB 생성
1. https://neon.tech → GitHub 로그인
2. New project: name=`talkpc-pro`, region=`Singapore`
3. Connection string 복사 → `server/.env` 의 `DATABASE_URL`

### 2. JWT 시크릿
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
출력 값을 `server/.env` 의 `JWT_SECRET` 에 넣음.

### 3. 로컬 DB 마이그레이션
```bash
cd server
pip install -r requirements.txt
alembic revision --autogenerate -m "init"
alembic upgrade head
```

### 4. 로컬 서버 실행
```bash
cd server
uvicorn main:app --reload --port 8000
```

### 5. Vercel 배포
- GitHub repo 연결: https://github.com/cho-y-j/talkpc-pro
- Root directory: `server`
- Environment variables: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRES_MIN`, `DEVICES_PER_USER`

### 6. 클라이언트
```bash
cd client
pip install -r requirements.txt
python main.py
```
환경변수 `TALKPC_API_BASE` 미설정 시 기본 production URL 사용. 개발 중엔 `http://localhost:8000`.

## 마일스톤

- [x] M0: 폴더 골격, server 인증 + 디바이스 등록, client 로그인 화면
- [ ] M1: 연락처 동기화 (/sync/contacts pull/push)
- [ ] M2: 템플릿 동기화 (/sync/templates)
- [ ] M3: 메인 발송 UI 통합 (talk-local 의 send_page 를 client/ui 로 통합)
- [ ] M4: 발송 로그 서버 전송 (send_logs)
- [ ] M5: 알림톡 발송 (세종 + UI)
- [ ] M6: 구독/결제 (만료형 라이선스)

## 빌드

추후 작성. talk-local 의 `TalkPC-Local.spec` 기반으로 client/main.py 진입점 변경 + auth/ui 모듈 hiddenimports 추가.
