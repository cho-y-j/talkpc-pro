"""생일 발송 중복 방지 로그.

3가지 발송 경로 (수동 즉시발송 / 카톡 OCR 스케줄러 / JSON 스케줄러) 가 같은
사람한테 같은 날 두 번 보내는 사고 방지. 발송 직전 `is_sent_today(name)`
체크 → 이미 보낸 사람이면 skip. 발송 성공 시 `mark_sent(name)` 기록.

저장: `data/birthday_sent.json`
   {
     "2026-06-04": ["김주홍", "이영자"],
     "2026-06-03": ["김주홍", "이영자"]
   }

7일 이상 지난 날짜는 자동 정리.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class BirthdaySentLog:
    """date(YYYY-MM-DD) → list[name] 저장. 스레드 안전."""

    def __init__(self, data_path: str):
        self.path = Path(data_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._data: dict[str, list[str]] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            if not isinstance(self._data, dict):
                self._data = {}
        except Exception:
            self._data = {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _normalize(name: str) -> str:
        """이름 정규화 — 공백 제거 + lowercase. OCR 노이즈 흡수용."""
        return (name or "").strip().replace(" ", "").lower()

    def is_sent_today(self, name: str, date: Optional[str] = None) -> bool:
        """오늘(또는 지정일) 이 사람한테 이미 보냈는지."""
        if not name:
            return False
        date = date or self._today()
        key = self._normalize(name)
        with self._lock:
            names = self._data.get(date, [])
            return any(self._normalize(n) == key for n in names)

    def mark_sent(self, name: str, date: Optional[str] = None):
        """발송 성공 기록. 중복 등록 안 함."""
        if not name:
            return
        date = date or self._today()
        with self._lock:
            names = self._data.setdefault(date, [])
            if not any(self._normalize(n) == self._normalize(name) for n in names):
                names.append(name)
            # 7일 이상 지난 항목 정리
            cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            for k in list(self._data.keys()):
                if k < cutoff:
                    del self._data[k]
            self._save()

    def get_today_sent(self, date: Optional[str] = None) -> list[str]:
        """오늘 발송된 이름 목록 (UI 표시용)."""
        date = date or self._today()
        with self._lock:
            return list(self._data.get(date, []))
