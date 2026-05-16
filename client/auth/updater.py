"""버전 체크 + 강제 업데이트 모달.

흐름:
  · 앱 시작 시 server /version?current=X.Y.Z 호출
  · requires_update=true → 강제 모달, 다운로드 URL 만 표시, 다른 진행 불가
  · is_outdated=true → 권장 안내 (닫고 사용 가능)
"""
import threading
import webbrowser
from tkinter import messagebox

import httpx


def check_version(api_base: str, current: str, timeout: float = 5.0) -> dict | None:
    """서버에 버전 체크 — 실패 시 None (네트워크 끊겼을 때 차단 안 함)."""
    try:
        r = httpx.get(f"{api_base.rstrip('/')}/version",
                        params={"current": current}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def show_update_dialog(info: dict, parent=None) -> bool:
    """업데이트 안내 모달.

    Returns:
        True: 사용자가 진행 OK / 권장 업데이트 닫음
        False: 강제 업데이트라 앱 종료해야 함
    """
    forced = info.get("requires_update", False)
    latest = info.get("latest", "?")
    url = info.get("download_url", "")
    notes = info.get("release_notes", "")

    if forced:
        msg = (
            f"필수 업데이트가 있습니다.\n\n"
            f"최신 버전: v{latest}\n"
            f"{notes}\n\n"
            f"다운로드 페이지를 열고 앱을 종료합니다."
        )
        messagebox.showwarning("업데이트 필요", msg, parent=parent)
        if url:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return False
    else:
        # 권장 업데이트
        msg = (
            f"새 버전이 있습니다 (v{latest}).\n"
            f"{notes}\n\n"
            f"지금 다운로드 페이지를 여시겠습니까?"
        )
        if messagebox.askyesno("업데이트 안내", msg, parent=parent):
            if url:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
        return True


def check_on_startup(api_base: str, current_version: str, parent=None) -> bool:
    """앱 시작 시 호출 — 강제 업데이트면 False 반환 (호출 측에서 sys.exit)."""
    info = check_version(api_base, current_version)
    if not info:
        return True  # 네트워크 끊김 등 → 진행 허용
    if info.get("requires_update"):
        show_update_dialog(info, parent=parent)
        return False
    if info.get("is_outdated"):
        # 비동기 — 첫 화면 막지 않게 별도 스레드 처리
        def _ask():
            show_update_dialog(info, parent=parent)
        threading.Timer(0.5, _ask).start()
    return True
