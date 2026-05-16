"""클라이언트 동기화 — pull/push + 로컬 캐시.

흐름:
  · 앱 시작/주기적으로 pull(since=last_sync_at) → 로컬 SQLite/JSON 업데이트
  · 사용자 편집 → 로컬 변경 + 큐에 쌓음
  · 5분마다 push(변경분) → 응답의 server_time 을 next-sync 기준으로 저장

여기는 API 호출 + 캐시 메타 관리만. 로컬 DB 통합은 client/core 의 ContactManager/MessageEngine 에서 처리.
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .api_client import ApiClient, ApiError
from .session import _data_dir


def _meta_path() -> Path:
    return _data_dir() / "sync_meta.json"


def load_last_sync_at() -> Optional[datetime]:
    p = _meta_path()
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("last_sync_at")
        return datetime.fromisoformat(ts) if ts else None
    except Exception:
        return None


def save_last_sync_at(ts: datetime):
    p = _meta_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"last_sync_at": ts.isoformat()}, f)


class SyncClient:
    """동기화 API 래퍼.

    실제 데이터 로컬 적용은 호출 측에서 on_pull / on_push 콜백으로 처리.
    """

    def __init__(self, api: ApiClient):
        self.api = api

    def pull(self) -> dict:
        """since=last_sync_at 으로 pull."""
        since = load_last_sync_at()
        params = {}
        if since:
            params["since"] = since.isoformat()
        url = "/sync/pull"
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode(params)
        result = self.api._request("GET", url)
        # server_time 을 last_sync_at 으로 저장
        if "server_time" in result:
            save_last_sync_at(datetime.fromisoformat(result["server_time"]))
        return result

    def push(self, contacts: list, templates: list,
              deleted_contact_ids: list[str] = None,
              deleted_template_ids: list[str] = None) -> dict:
        """변경분 push."""
        body = {
            "contacts": contacts,
            "templates": templates,
            "deleted_contact_ids": deleted_contact_ids or [],
            "deleted_template_ids": deleted_template_ids or [],
        }
        result = self.api._request("POST", "/sync/push", json=body)
        if "server_time" in result:
            save_last_sync_at(datetime.fromisoformat(result["server_time"]))
        return result


class AutoSyncWorker:
    """5분 주기 자동 pull + push (변경분 콜백으로 수집).

    Usage:
        worker = AutoSyncWorker(
            sync_client,
            on_pull=lambda data: apply_to_local(data),
            collect_changes=lambda: get_pending_changes(),
        )
        worker.start()
    """

    INTERVAL_SEC = 300  # 5분

    def __init__(self, sync: SyncClient,
                  on_pull: Optional[Callable[[dict], None]] = None,
                  collect_changes: Optional[Callable[[], dict]] = None):
        self.sync = sync
        self.on_pull = on_pull
        self.collect_changes = collect_changes
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

    def trigger_now(self):
        """즉시 1회 sync (별도 스레드)."""
        threading.Thread(target=self._cycle, daemon=True).start()

    def _cycle(self):
        # 1. pull
        try:
            data = self.sync.pull()
            if self.on_pull:
                self.on_pull(data)
        except ApiError:
            pass
        except Exception:
            pass
        # 2. push (변경분 있을 때만)
        if self.collect_changes:
            try:
                changes = self.collect_changes()
                if (changes.get("contacts") or changes.get("templates")
                        or changes.get("deleted_contact_ids")
                        or changes.get("deleted_template_ids")):
                    self.sync.push(**changes)
            except Exception:
                pass

    def _run(self):
        while not self._stop.is_set():
            self._cycle()
            for _ in range(self.INTERVAL_SEC):
                if self._stop.is_set():
                    return
                time.sleep(1)
