"""TalkPC Pro 클라이언트 진입점.

흐름:
  1. LoginWindow 표시 → 토큰 캐시 있으면 자동 검증
  2. 인증 성공 → talk-local 기반 메인 앱 (Orchestrator + App) 띄움
"""
import sys
import os
from pathlib import Path


def get_project_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


def launch_main_app(api, license_key: str):
    """로그인 성공 후 메인 카톡 발송 앱 실행."""
    from core.orchestrator import Orchestrator
    # NOTE: ui.app 은 talk-local 에서 가져와야 — 차후 client/ui/app.py 로 통합
    print(f"로그인 완료. license={license_key}")
    print("→ 메인 앱 통합 작업 진행 중. 다음 마일스톤에서 카톡 발송 UI 연결.")


def main():
    from ui.login_page import LoginWindow
    win = LoginWindow(on_success=launch_main_app)
    win.mainloop()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
