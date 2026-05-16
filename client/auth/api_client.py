"""서버 API 클라이언트 — httpx 동기 호출."""
import os
from typing import Optional

import httpx


DEFAULT_BASE = "https://talkpc-pro.vercel.app"  # 배포 후 실제 URL 로 교체


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


class ApiClient:
    def __init__(self, base_url: Optional[str] = None,
                  access_token: Optional[str] = None):
        self.base = (base_url or os.environ.get("TALKPC_API_BASE")
                      or DEFAULT_BASE).rstrip("/")
        self.token = access_token
        self._client = httpx.Client(timeout=15.0)

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base}{path}"
        try:
            resp = self._client.request(method, url, headers=self._headers(),
                                          **kwargs)
        except httpx.HTTPError as e:
            raise ApiError(0, f"네트워크 오류: {e}")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ApiError(resp.status_code, str(detail))
        return resp.json() if resp.content else {}

    # ── 인증 ──

    def signup(self, email: str, password: str) -> dict:
        """가입 — 응답의 status='pending' 예상. 토큰 발급 안 됨."""
        return self._request("POST", "/auth/signup",
                              json={"email": email, "password": password})

    def login(self, email: str, password: str, hwid: str,
               hostname: str = "") -> dict:
        """로그인 — active 사용자만 토큰 발급."""
        return self._request("POST", "/auth/login", json={
            "email": email, "password": password,
            "hwid": hwid, "hostname": hostname,
        })

    def heartbeat(self, hwid: str) -> dict:
        """3분마다 호출 — 상태 변화 즉시 감지 + last_seen 갱신."""
        return self._request("POST", "/auth/heartbeat", json={"hwid": hwid})

    def list_devices(self) -> list[dict]:
        return self._request("GET", "/auth/devices")

    def remove_device(self, device_id: str) -> dict:
        return self._request("DELETE", f"/auth/devices/{device_id}")

    def health(self) -> dict:
        return self._request("GET", "/health")
