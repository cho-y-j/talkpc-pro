"""활동 표시줄 (BusyBar).

장시간 작업(친구수집/생일발송/일반발송/엑셀처리 등) 중에 사용자가
"작동 중인지 멈췄는지" 알 수 있도록 최상단에 표시되는 띠.

특징:
- 좌측: 회전하는 스피너(⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏) — 화면 갱신=살아있음 증거
- 가운데: 현재 작업 상태 + 마지막 로그 한 줄 (변동)
- 우측: 진행률(X/Y) + 중지 버튼

`orchestrator.on_state_change`, `on_progress`, `on_log` 콜백으로 자동 갱신.
사용자는 별도 조작 없이 진행 상황 확인 가능.
"""
from __future__ import annotations

import customtkinter as ctk
from ui.theme import AppTheme as T


# Braille 스피너 — 8 프레임 부드럽게
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_TICK_MS = 100   # 스피너 회전 주기
_AUTO_HIDE_MS = 3500  # COMPLETED/ERROR 표시 후 자동 숨김


class BusyBar(ctk.CTkFrame):
    """상단 활동 표시줄.

    사용:
        bar = BusyBar(parent, on_cancel=lambda: orchestrator.stop_sending())
        bar.grid(...)
        # orchestrator.on_state_change(bar.on_state)
        # orchestrator.on_progress(bar.on_progress)
        # orchestrator.on_log(bar.on_log)
    """

    def __init__(self, master, on_cancel=None, **kwargs):
        super().__init__(
            master,
            fg_color=T.BG_CARD,
            height=34,
            corner_radius=0,
            **kwargs,
        )
        self._on_cancel = on_cancel
        self._state = "idle"
        self._spinner_index = 0
        self._spinner_running = False
        self._auto_hide_after_id = None

        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        # 좌측: 스피너 + 상태 라벨
        self.spinner_label = ctk.CTkLabel(
            self, text="●", width=20,
            font=(T.get_font_family(), 14, "bold"),
            text_color=T.TEXT_MUTED,
        )
        self.spinner_label.grid(row=0, column=0, padx=(12, 6), sticky="w")

        # 중앙: 메시지
        self.message_label = ctk.CTkLabel(
            self, text="대기 중",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_SECONDARY,
            anchor="w",
        )
        self.message_label.grid(row=0, column=1, padx=4, sticky="ew")

        # 우측: 진행률
        self.progress_label = ctk.CTkLabel(
            self, text="",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            text_color=T.ACCENT,
        )
        self.progress_label.grid(row=0, column=2, padx=(6, 6), sticky="e")

        # 우측: 중지 버튼 (idle 일 땐 숨김)
        self.cancel_btn = ctk.CTkButton(
            self, text="중지", width=56, height=24,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            fg_color=T.ACTION_DANGER, hover_color=T.ACTION_DANGER_HOVER,
            text_color=T.TEXT_ON_DARK, corner_radius=4,
            command=self._handle_cancel,
        )
        # 처음엔 숨김 — _set_busy 시 표시
        self._cancel_visible = False

    # ── 외부 콜백 진입점 (orchestrator hooks) ──

    def on_state(self, state: str):
        """orchestrator.on_state_change 등록용."""
        self._state = state
        self.after(0, self._refresh)

    def on_progress(self, current: int, total: int, name: str = ""):
        """orchestrator.on_progress 등록용."""
        def _u():
            if total > 0:
                self.progress_label.configure(text=f"{current}/{total}")
            else:
                self.progress_label.configure(text=f"#{current}")
            if name:
                self.message_label.configure(text=f"{name}")
        self.after(0, _u)

    def on_log(self, message: str, level: str = "info"):
        """orchestrator.on_log 등록용. 최신 로그 1줄 중앙에 표시."""
        # 너무 긴 로그는 자름
        text = (message or "").replace("\n", " ")[:90]
        if not text:
            return
        def _u():
            self.message_label.configure(text=text)
        self.after(0, _u)

    # ── 내부 동작 ──

    def _refresh(self):
        """state 기반 시각 표시 갱신."""
        # 이전 자동숨김 예약 취소
        if self._auto_hide_after_id is not None:
            try:
                self.after_cancel(self._auto_hide_after_id)
            except Exception:
                pass
            self._auto_hide_after_id = None

        busy_states = {"initializing", "sending", "paused"}
        if self._state in busy_states:
            self._set_busy()
        elif self._state == "completed":
            self._set_completed()
        elif self._state == "error":
            self._set_error()
        else:
            self._set_idle()

    def _set_idle(self):
        self._spinner_running = False
        self.spinner_label.configure(text="●", text_color=T.TEXT_MUTED)
        self.message_label.configure(text="대기 중", text_color=T.TEXT_SECONDARY)
        self.progress_label.configure(text="")
        self._hide_cancel()

    def _set_busy(self):
        if not self._spinner_running:
            self._spinner_running = True
            self._tick_spinner()
        self.message_label.configure(text_color=T.TEXT_PRIMARY)
        self._show_cancel()

    def _set_completed(self):
        self._spinner_running = False
        self.spinner_label.configure(text="✓", text_color=T.SUCCESS)
        self.message_label.configure(
            text="완료", text_color=T.SUCCESS,
        )
        self.progress_label.configure(text="")
        self._hide_cancel()
        # 3.5초 후 idle 로 복귀
        self._auto_hide_after_id = self.after(_AUTO_HIDE_MS, self._set_idle)

    def _set_error(self):
        self._spinner_running = False
        self.spinner_label.configure(text="✗", text_color=T.ERROR)
        self.message_label.configure(text_color=T.ERROR)
        self._hide_cancel()
        self._auto_hide_after_id = self.after(_AUTO_HIDE_MS, self._set_idle)

    def _show_cancel(self):
        if not self._cancel_visible:
            self.cancel_btn.grid(row=0, column=3, padx=(6, 10), sticky="e")
            self._cancel_visible = True

    def _hide_cancel(self):
        if self._cancel_visible:
            self.cancel_btn.grid_forget()
            self._cancel_visible = False

    def _tick_spinner(self):
        if not self._spinner_running:
            return
        frame = _SPINNER_FRAMES[self._spinner_index % len(_SPINNER_FRAMES)]
        self.spinner_label.configure(text=frame, text_color=T.ACCENT)
        self._spinner_index += 1
        self.after(_TICK_MS, self._tick_spinner)

    def _handle_cancel(self):
        if self._on_cancel:
            try:
                self._on_cancel()
                self.message_label.configure(text="중지 요청됨...", text_color=T.WARNING)
            except Exception as e:
                self.message_label.configure(text=f"중지 실패: {e}", text_color=T.ERROR)
