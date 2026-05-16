"""TalkPC Pro 클라이언트 진입점.

흐름:
  1. LoginWindow 표시 → 토큰 캐시 있으면 자동 검증 (heartbeat)
  2. 인증 성공 → 메인 앱 + heartbeat 백그라운드 스레드 시작
"""
import sys
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


def get_project_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


_heartbeat_worker = None  # 전역 — 앱 종료 시 stop


def launch_main_app(api, license_key: str):
    """로그인 성공 후 메인 카톡 발송 앱 실행."""
    global _heartbeat_worker
    from auth import HeartbeatWorker, SessionStore

    session = SessionStore()

    # heartbeat 스레드 시작 — 서버가 비활성 응답하면 앱 강제 종료
    def _on_invalid(message: str):
        try:
            session.clear()
        except Exception:
            pass
        # tkinter 메인 스레드에 띄우기 (background 스레드에서 messagebox 직접 호출 X)
        root = tk._default_root
        if root:
            root.after(0, lambda: (
                messagebox.showwarning("세션 만료", message),
                root.destroy(),
            ))
        else:
            print(f"[세션 만료] {message}")

    _heartbeat_worker = HeartbeatWorker(api, on_invalid=_on_invalid)
    _heartbeat_worker.start()

    # NOTE: 메인 발송 UI 는 M4 에서 통합. 지금은 placeholder.
    print(f"✓ 로그인 완료. license={license_key}")
    print("→ heartbeat 백그라운드 시작 (3분 주기).")
    print("→ 메인 발송 UI 는 M4 에서 통합 예정.")

    # 임시 placeholder 창 (M4 까지 임시 — 그 후 메인 앱 통합)
    import customtkinter as ctk
    win = ctk.CTk()
    win.title("TalkPC Pro")
    win.geometry("500x300")
    ctk.CTkLabel(win, text="✓ 로그인 완료",
                  font=("Helvetica", 18, "bold")).pack(pady=20)
    ctk.CTkLabel(win, text=f"라이선스: {license_key}",
                  font=("Helvetica", 11)).pack(pady=4)
    ctk.CTkLabel(win, text="발송 UI 는 M4 에서 통합 예정",
                  font=("Helvetica", 10), text_color="#888").pack(pady=20)
    def _on_close():
        if _heartbeat_worker:
            _heartbeat_worker.stop()
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", _on_close)
    win.mainloop()


def main():
    from ui.login_page import LoginWindow
    win = LoginWindow(on_success=launch_main_app)
    win.mainloop()
    if _heartbeat_worker:
        _heartbeat_worker.stop()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
