"""세션 로컬 저장소 — JWT 토큰 + 라이선스 키.

저장 위치: %APPDATA%\talkpc-pro\session.json (Windows)
사용자 폴더에 두면 재설치/exe 위치 변경에도 유지.
"""
import json
import os
from pathlib import Path
from typing import Optional


def _data_dir() -> Path:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = Path(appdata) / "talkpc-pro"
    d.mkdir(parents=True, exist_ok=True)
    return d


class SessionStore:
    """단순 파일 저장 — 토큰/라이선스/사용자ID."""

    def __init__(self):
        self.path = _data_dir() / "session.json"

    def load(self) -> Optional[dict]:
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save(self, access_token: str, license_key: str, user_id: str,
              email: str = ""):
        data = {
            "access_token": access_token,
            "license_key": license_key,
            "user_id": user_id,
            "email": email,
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def clear(self):
        if self.path.exists():
            self.path.unlink()
