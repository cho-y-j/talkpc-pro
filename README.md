# TalkPC Pro

`talk-local` (오프라인 카톡 자동 발송) 의 상용판. 로그인/구독/서버 DB/알림톡 추가.

## 비전

- **로그인 기반 사용자 식별** — 무단 복제 방지
- **서버 DB** — 연락처/템플릿/발송 기록을 클라우드 보관, 재설치 후에도 복구
- **알림톡 발송** — 카톡 자동화 외에 정식 알림톡 채널 추가 (세종텔레콤)
- **고객/템플릿 고급 관리** — 카테고리/태그/공유/통계

## 디렉토리

```
talkpc-pro/
├── client/              # PC 클라이언트 (Python + customtkinter)
│   ├── core/            # 카톡 자동화 (talk-local 핵심 모듈 fork)
│   ├── ui/              # 로그인 화면 + 기존 발송 UI 확장
│   ├── auth/            # 서버 인증/세션/로컬 토큰 캐시
│   └── main.py
├── server/              # 백엔드 (FastAPI)
│   ├── api/             # /auth, /contacts, /templates, /sync 엔드포인트
│   ├── models/          # SQLAlchemy 모델
│   └── migrations/      # Alembic
├── shared/              # 클라이언트-서버 공통 스키마/상수
└── docs/                # 아키텍처, API 명세
```

## 핵심 관계

```
talk-local (오프라인 v1.0-stable, 동결)
     │
     │ core 모듈 fork (kakao_friends, kakao_sender, paddle_ocr_helper, ...)
     ▼
talkpc-pro/client/  ──── HTTPS ────▶  talkpc-pro/server/  ◀──── PostgreSQL
```

## 결정 필요 항목 (시작 전)

| 항목 | 옵션 | 임시 기본 |
|---|---|---|
| 백엔드 호스팅 | Supabase / 자체 (VPS) / Vercel+Neon / 세종텔레콤 DB 옆 | **Supabase** (가장 빠름) |
| 인증 방식 | 이메일+비번 / 카카오 OAuth / 라이선스 키 | **이메일+비번 + 라이선스 키** |
| 라이선스 정책 | 디바이스 1대 고정 / 사용자 N대 / 만료형 구독 | **사용자 1인 1대** (HWID 묶기) |
| 알림톡 발송 | 세종텔레콤 단독 / 다중 채널 | **세종 단독** (기존 sejong_sender 확장) |

이 4가지 결정 후에 본격 작업 시작 — 결정 안 한 항목은 임시 기본값으로 진행.
