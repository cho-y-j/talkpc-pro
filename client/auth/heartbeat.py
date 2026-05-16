"""백그라운드 heartbeat — 3분마다 서버에 상태 확인.

서버가 status != active 응답하면 메인 앱에 알리는 콜백 호출.
"""
import threading
import time
from typing import Callable, Optional

from .api_client import ApiClient, ApiError
from .hwid import get_hwid


class HeartbeatWorker:
    """별도 스레드로 heartbeat 주기 호출.

    Usage:
        worker = HeartbeatWorker(api, on_invalid=lambda msg: ...)
        worker.start()
        ...
        worker.stop()
    """

    INTERVAL_SEC = 180  # 3분

    def __init__(self, api: ApiClient,
                  on_invalid: Optional[Callable[[str], None]] = None):
        self.api = api
        self.on_invalid = on_invalid
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        hwid = get_hwid()
        while not self._stop.is_set():
            try:
                self.api.heartbeat(hwid)
            except ApiError as e:
                # 403 = 상태 비활성, 401 = 토큰 만료
                if e.status in (401, 403) and self.on_invalid:
                    self.on_invalid(e.message)
                    return  # 더 이상 호출 안 함
            except Exception:
                pass  # 네트워크 일시 오류는 무시 (다음 사이클 재시도)
            # 짧게 쪼개서 sleep — stop 신호 빠르게 반응
            for _ in range(self.INTERVAL_SEC):
                if self._stop.is_set():
                    return
                time.sleep(1)
