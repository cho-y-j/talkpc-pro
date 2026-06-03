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

## 빌드 정책 (v0.1.8 부터 확정)

### 원칙: 로컬 빌드 우선, CI 는 보조
v0.1.5~0.1.7 동안 CI 빌드 3연속 깨짐 — 원인 = `requirements.txt` 에 Cython
미핀 + pip 가 매 빌드마다 최신 Cython 설치. v0.1.4 시점 이후 Cython 3.2.x
릴리스로 paddleocr 2.7.3 의 컴파일된 `.pyd` 와 ABI 불일치(`TransitionMap
size changed`). dev PC 에서 source mode 는 동작했지만 frozen exe 만 깨짐.

→ **로컬에서 빌드 + 동작 검증 후 GitHub Release 에 수동 업로드** 가 가장 안전.
CI 는 백업/이중 검증용. 모든 OCR/Paddle 의존 버전은 `requirements.txt` 에
핀(고정) 필수.

### 핀 필수 의존성 (절대 풀지 말 것)
```
Cython==3.0.10        # paddleocr 2.7.3 컴파일 확장과 ABI 호환
paddlepaddle==2.6.2
paddleocr==2.7.3
numpy<2.0
opencv-python-headless<4.10
```

### 로컬 빌드 절차
```powershell
# 1. PyInstaller (~7분)
cd D:\talkpc\talkpc-pro\client
pyinstaller TalkPC-Pro.spec --noconfirm
# → D:\talkpc\talkpc-pro\client\dist\TalkPC-Pro\ (~730MB)

# 2. 자가검증 — frozen exe 의 Paddle init 확인 (필수)
$log = "$env:TEMP\kakao_win32_debug.log"; Remove-Item $log -EA SilentlyContinue
Start-Process .\dist\TalkPC-Pro\TalkPC-Pro.exe; Start-Sleep 25
Stop-Process -Name TalkPC-Pro -Force
Get-Content $log -Tail 5
# 기대 출력:
#   [STARTUP] frozen=True paddle_available=True
#   [OCR] PaddleOCR 초기화 성공
#   [STARTUP] PaddleOCR 인스턴스: OK(정상)

# 3. zip 패키징
Compress-Archive -Path .\dist\TalkPC-Pro\* `
  -DestinationPath .\dist\TalkPC-Pro-windows-x64.zip -Force

# 4. Inno Setup (Setup.exe — ~3분)
# 사전: winget install JRSoftware.InnoSetup -e (1회만)
# .iss 의 #define MyAppVersion "0.1.x" 갱신
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
cd D:\talkpc\talkpc-pro\installer
& $iscc /O"C:\Temp\talkpc-installer" TalkPC-Pro.iss
# D 드라이브 공간 부족하면 /O 로 C 로 우회 (Inno LZMA2 ultra64 = 큰 작업 영역)

# 5. GitHub Release 업로드 (gh CLI)
gh release create v0.1.x `
  ".\client\dist\TalkPC-Pro-windows-x64.zip" `
  "C:\Temp\talkpc-installer\TalkPC-Pro-Setup.exe" `
  --target main --title "TalkPC Pro v0.1.x" --notes "..."
# 또는 기존 release 에 --clobber 로 덮어쓰기:
gh release upload v0.1.x <파일> --clobber
```

### Vercel /download 페이지 기대 파일명
`landing/app/download/page.tsx` 가 GitHub `releases/latest/download/` 의
고정 파일명을 직접 링크 — 표준 파일명 유지 필수:
- `TalkPC-Pro-Setup.exe`
- `TalkPC-Pro-windows-x64.zip`

(버전 포함 파일명은 Vercel 페이지에서 못 찾음. 업로드 시 비버전 파일명으로.)

### CI 빌드 (보조)
- `.github/workflows/release.yml` — 태그 푸시 시 자동
- Cython 핀 추가 후엔 정상 동작 가능. 단 로컬 검증 본을 우선으로 함.
- CI artifacts 가 로컬 본을 덮어쓸 위험 — 같은 태그 작업 시 충돌 주의.

## 생일 자동발송 아키텍처 (v0.1.11 확정 — 2026-06-03)

### 흐름 — 수동/스케줄러 동일

```
orchestrator.run_kakao_birthday_send(dry_run=...)
  └─ kakao_friends.send_birthday_messages(...)
       ├─ ensure_ready_state(친구탭 자동 전환 + 검색창 닫기)
       ├─ Phase 1: _scan_birthday_section()
       │     └─ click_first_birthday() + ↓ 로 birthday 섹션 enumerate
       │     └─ today_rows / other_rows 분리
       └─ Phase 2 (실발송): for nth, target in enumerate(today_rows):
             _navigate_to_nth_today_birthday(nth)
             _process_birthday_target() → sender.send_to_current_selection()
```

**핵심 원칙**:
- **Scan 한 번 → N명 확정 → 정확히 N번 발송 → 종료.** 끝없이 헤매기 없음.
- 스케줄러도 같은 코드 경로 (수동과 동일).

### sender 자동 초기화 (스케줄러 경로 필수)

`orchestrator.__init__` 시점에 `self.sender = None`. `confirm_calibration()` 호출 시
초기화. 스케줄러 자동발화 시점엔 confirm_calibration 미호출 가능 →
`run_kakao_birthday_send` 시작에 lazy init:

```python
if self.sender is None:
    self.load_coordinates_auto_first()
    self.sender = KakaoSender(self.coordinates, self.config)
    if self._kakao_friends is not None:
        self._kakao_friends.set_sender(self.sender)
```

이 없으면 chat_hwnd 분리 안 됨 → main 의 X 버튼/광고 클릭으로 카톡 닫히는
사고 (kakao_sender go_back 주석 참조).

### Scheduler — 시작 grace 90초

`scheduler._check_daily_auto_send`:
- 앱 시작 시각(`_startup_time`) 기록
- 시작 후 90초 안엔 무조건 skip (사용자가 새 시간 저장할 시간 확보)
- 매 체크마다 `self.load()` — UI 에서 시간 바꾸면 즉시 반영

**없으면**: 재시작 직후 stale 설정(이전 시각)으로 즉시 트리거 → 사용자가
새 시간 저장하기 전에 발화 → 의도와 다른 시점 발송.

### ensure_ready_state — 자동 친구탭 복귀

`send_birthday_messages` 시작에서 호출:

```python
self.ensure_ready_state(
    friends_icon=self.sender.coords.get("friends_tab_icon"),
    search_icon=self.sender.coords.get("search_icon"),
)
```

내부에서 `_click_friends_tab_icon` (사람아이콘 stealth click) → OCR 로
친구탭 활성 검증 → 안 됐으면 1회 재시도. 검색창 열려있으면 search_icon
토글로 닫기.

**`_click_friends_tab_icon` 주의**: stealth click 전 반드시 `activate(main_hwnd)`.
백그라운드/다른 창 포그라운드 상태에선 클릭이 엉뚱한 창으로 가서 탭 전환
실패. (스케줄러 자동발송 시 TalkPC-Pro UI 가 가로채는 케이스)

### sender.send_to_current_selection() — 신규 메서드

`kakao_sender.py` 에 추가. ↓ 키로 selection 박힌 친구에게 메시지 발송.
이름 검색 없음 (동명이인 회피). 흐름:

1. `activate(main_hwnd) + keybd_event Enter` (글로벌 키, PostMessage 안 먹힘)
2. `get_foreground_as_chat()` → chat_hwnd. **main_hwnd 와 같으면 abort**
   (좌표 클릭이 메인의 X/광고 누르는 사고 방지).
3. `position_chat_to_main()` → 채팅창을 main 위치로
4. `type_message()` (message_input 좌표 stealth click + paste_text)
5. `send_message()` (send_enter 좌표 stealth click)
6. `paste_image()` (선택)
7. `go_back()` (back_button 좌표 stealth click on chat_hwnd)
8. `activate(main_hwnd)` — 다음 ↓ navigate 가 main 친구탭에 먹히게

**OCR 경고팝업 자동감지 호출 X**: `detect_warning_popup()` 가 friend tab
안내문 "친구의 생일을 **확인해** 보세요" 또는 TalkPC-Pro 설정 dialog 의
"확인" 단어를 잡아 false positive 차단되는 사고 → 호출 제거.

### 일자 분류 — yesterday / tomorrow 구분

`_classify_row_text` 가 "어제/그제" → `"yesterday"`, "내일/모레" →
`"tomorrow"` 분리. (이전엔 `"other"` 통합 → `_sync_birthday_to_contacts`
의 `DAY_MMDD["yesterday"]/"tomorrow"` 매칭 실패 → DB 자동저장 안 됨)

매일 실행 시 ±1일 생일자 = 3일치 동시 수집 → ~120일이면 1년치 완성.

### `_navigate_to_nth_today_birthday(n)` — 매 발송마다 처음부터

```python
def _navigate_to_nth_today_birthday(self, n):
    click_first_birthday() → 첫 생일자 도달
    if n == 0 and first.day == "today": return True
    # n>0: ↓ 키로 today 카운트하며 n번째까지
```

매번 처음부터 navigate — 신버전 카톡이 발송 후 selection 손실 + 생일자
숨김 동작 안전하게 처리. 매 ↓ 전 `activate(main_hwnd)` 필수.

### `click_first_birthday` — ↓ 키 + seed click

- `reset_to_top()` + 본인 프로필 행에 **stealth seed click** (selection 박기)
- `navigate_step()` 반복 → birthday day=today 발견 시 selection 위치에서 return
- `friend` 분류 행은 통과 (프로필도 friend 로 분류됨)
- MAX_STEPS=15, MAX_CONSECUTIVE_NO_MOVE=3

### 디버깅 절차

문제 발생 시 1순위 — `%TEMP%\kakao_win32_debug.log` 확인.
- `[STARTUP] PaddleOCR 인스턴스: OK` — Paddle 정상
- `send_birthday_messages: sender=True` — sender 주입 확인
- `_click_friends_tab_icon: 검증 OK` — 친구탭 전환 성공
- `_scan_birthday_section: scan 완료 — today=N other=M` — 발견 카운트
- `_navigate_to_nth(n=K): 도달 — selection='XXX'` — 정확한 도달
- `채팅창 감지: hwnd=다른값 title='XXX'` — main 과 다른 hwnd 면 정상
- `send_to_current_selection: 완료` — 정상 종료

## 로그/캡처 누적 방지 정책 (v0.1.8)

상용 배포에서 무한 누적 디스크 점유 방지. **발송/수집 이력은 보존**:
- `kakao_win32_debug.log`: 5MB 도달 시 `.old` 회전 (총 ~10MB 상한)
- `logs/sync_rows/`: 친구 수집 시작 시 폴더 정리 (이번 run 만 유지)
- `logs/verify_failed/`: 최근 50개 캡처만 유지
- `logs/screenshots/`: 최근 50개만 유지
- `logs/kakao_runs/*.json`: **유지** (발송/수집 이력)
- `logs/session_*.json`: **유지** (발송 세션 결과)
