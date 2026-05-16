"""TalkPC Pro 클라이언트 진입점.

흐름:
  1. 버전 체크 → 강제 업데이트면 종료
  2. LoginWindow → 가입/로그인 / pending 안내
  3. 인증 성공 → Orchestrator + 메인 App + heartbeat + 자동 sync
"""
import sys
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


# ── 경로 ──

def get_project_root():
    """exe 실행 시 exe 옆 폴더, 스크립트 실행 시 스크립트 폴더."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


def get_bundle_dir():
    """PyInstaller 번들 리소스 (config/tessdata, paddle_models)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS",
                              Path(sys.executable).parent / "_internal")).resolve()
    return Path(__file__).parent.resolve()


PROJECT_ROOT = get_project_root()
BUNDLE_DIR = get_bundle_dir()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


# ── frozen 초기 파일 복사 (talk-local 와 동일 정책) ──

def _seed_initial_files():
    """exe 첫 실행: 번들 → 사용자 폴더로 초기 파일 풀기."""
    if not getattr(sys, "frozen", False):
        return
    import shutil
    # 디렉토리 생성
    for d in ["config", "data/templates", "logs/screenshots"]:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)
    # tessdata
    src = BUNDLE_DIR / "config" / "tessdata"
    dst = PROJECT_ROOT / "config" / "tessdata"
    if src.exists() and not dst.exists():
        shutil.copytree(str(src), str(dst))
    # default_config.json
    src = BUNDLE_DIR / "config" / "default_config.json"
    dst = PROJECT_ROOT / "config" / "default_config.json"
    if src.exists() and not dst.exists():
        shutil.copy2(str(src), str(dst))
    # learned_positions.json (빌드 시 dev 학습 좌표가 기본값)
    src = BUNDLE_DIR / "config" / "learned_positions.json"
    dst = PROJECT_ROOT / "config" / "learned_positions.json"
    if src.exists() and not dst.exists():
        shutil.copy2(str(src), str(dst))
    # data/ 시드 (없는 파일만)
    bundle_data = BUNDLE_DIR / "data"
    local_data = PROJECT_ROOT / "data"
    if bundle_data.exists():
        for s in bundle_data.rglob("*"):
            if s.is_dir():
                continue
            rel = s.relative_to(bundle_data)
            d = local_data / rel
            if not d.exists():
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(s), str(d))


def _check_deps():
    missing = []
    for pkg in ["customtkinter", "pyautogui", "PIL", "openpyxl", "httpx"]:
        try:
            __import__(pkg)
        except ImportError:
            name_map = {"PIL": "Pillow"}
            missing.append(name_map.get(pkg, pkg))
    if missing:
        print(f"누락된 패키지: pip install {' '.join(missing)}")
        sys.exit(1)


# ── 메인 ──

# 전역 — App 종료 시 stop 호출
_heartbeat_worker = None
_sync_worker = None
_app_instance = None


def launch_main_app(api, license_key: str):
    """로그인 성공 후 호출. Orchestrator + App + 백그라운드 워커 시작."""
    global _heartbeat_worker, _sync_worker, _app_instance

    from auth import HeartbeatWorker, SyncClient, AutoSyncWorker, SessionStore
    from core.orchestrator import Orchestrator
    from ui.app import App

    session = SessionStore()

    # ── heartbeat: 3분마다 서버 상태 체크 ──
    def _on_invalid(message: str):
        try:
            session.clear()
        except Exception:
            pass
        # 메인 스레드에서 안전하게 종료
        if _app_instance:
            try:
                _app_instance.after(0, lambda: (
                    messagebox.showwarning("세션 만료", message),
                    _app_instance.destroy(),
                ))
            except Exception:
                pass

    _heartbeat_worker = HeartbeatWorker(api, on_invalid=_on_invalid)
    _heartbeat_worker.start()

    # ── Orchestrator (talk-local 검증된 발송 엔진) ──
    orchestrator = Orchestrator(base_dir=str(PROJECT_ROOT))
    orchestrator.api_client = api          # 발송 로그 전송용
    orchestrator.license_key = license_key

    # ── 발송 결과를 send_logs API 로 전송 ──
    def _on_result(result: dict):
        try:
            api._request("POST", "/logs", json={
                "contact_name": result.get("contact_name", "")[:64],
                "channel": "kakao_bot",
                "status": result.get("status", "")[:16],
                "message_preview": (result.get("message") or "")[:200],
                "detail": (result.get("detail") or "")[:1000],
            })
        except Exception:
            pass  # 로그 전송 실패는 발송 자체 막지 않음

    orchestrator.on_result(_on_result)

    # ── 자동 동기화 (5분 주기) ──
    sync = SyncClient(api)

    def _apply_pull(data: dict):
        """서버 → 로컬: 연락처/템플릿 덮어쓰기.

        단순 LWW — 서버에 변경된 것이 있으면 그대로 로컬 적용.
        """
        try:
            cm = orchestrator.contact_mgr
            me = orchestrator.message_engine
            # 연락처 머지 (id 기준)
            from core.contact_manager import Contact as _C
            for c_dto in data.get("contacts", []):
                existing = next((c for c in cm.get_all()
                                  if c.id == c_dto.get("id")), None)
                if existing:
                    for k, v in c_dto.items():
                        if k == "id":
                            continue
                        if hasattr(existing, k):
                            setattr(existing, k, v)
                else:
                    c = _C(
                        name=c_dto.get("name", ""),
                        category=c_dto.get("category", "friend"),
                        phone=c_dto.get("phone", ""),
                        company=c_dto.get("company", ""),
                        position=c_dto.get("position", ""),
                        memo=c_dto.get("memo", ""),
                        birthday=c_dto.get("birthday", ""),
                        anniversary=c_dto.get("anniversary", ""),
                        contact_id=c_dto.get("id"),
                    )
                    cm.contacts.append(c)
            cm.save()
            # 템플릿 머지
            for t_dto in data.get("templates", []):
                existing = next((t for t in me.templates
                                  if t.id == t_dto.get("id")), None)
                if existing:
                    existing.name = t_dto.get("name", existing.name)
                    existing.contents = t_dto.get("contents",
                                                    existing.contents)
                    existing.category = t_dto.get("category",
                                                    existing.category)
                    existing.image_path = t_dto.get("image_path",
                                                     existing.image_path)
                else:
                    from core.message_engine import MessageTemplate
                    me.templates.append(MessageTemplate.from_dict(t_dto))
            me.save_templates()
        except Exception as e:
            print(f"sync pull 적용 실패: {e}")

    def _collect_push():
        """로컬 → 서버: 전체 contacts/templates 단순 push.

        간단 구현 — 진짜 변경분만 보내려면 dirty 플래그 필요.
        주기적이라 큰 비용 아님.
        """
        try:
            return {
                "contacts": [c.to_dict() for c in orchestrator.contact_mgr.get_all()],
                "templates": [t.to_dict() for t in orchestrator.message_engine.templates],
            }
        except Exception:
            return {"contacts": [], "templates": []}

    _sync_worker = AutoSyncWorker(sync, on_pull=_apply_pull,
                                    collect_changes=_collect_push)
    _sync_worker.trigger_now()  # 즉시 1회 (서버 데이터 받아옴)
    _sync_worker.start()        # 5분 주기

    # ── 메인 App ──
    _app_instance = App(orchestrator=orchestrator)
    _app_instance.title(f"TalkPC Pro — {license_key}")

    # 종료 시 워커 정리
    original_close = _app_instance._on_close
    def _on_close_extended():
        if _heartbeat_worker:
            _heartbeat_worker.stop()
        if _sync_worker:
            _sync_worker.stop()
        original_close()
    _app_instance.protocol("WM_DELETE_WINDOW", _on_close_extended)
    _app_instance.mainloop()


def main():
    print("=" * 40)
    print("  TalkPC Pro v0.1.0")
    print("=" * 40)
    print(f"  frozen: {getattr(sys, 'frozen', False)}")
    print(f"  ROOT: {PROJECT_ROOT}")
    print("=" * 40)

    _check_deps()
    _seed_initial_files()

    # 시작 시 버전 체크 — 강제 업데이트면 즉시 종료
    from auth.updater import check_on_startup
    from auth.api_client import DEFAULT_BASE
    from version import __version__
    api_base = os.environ.get("TALKPC_API_BASE") or DEFAULT_BASE
    if not check_on_startup(api_base, __version__):
        return

    # 로그인
    from ui.login_page import LoginWindow
    win = LoginWindow(on_success=launch_main_app)
    win.mainloop()

    if _heartbeat_worker:
        _heartbeat_worker.stop()
    if _sync_worker:
        _sync_worker.stop()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
