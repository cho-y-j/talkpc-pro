"""
App - 로컬 전용 메인 애플리케이션
카카오톡 자동 발송 (서버 연동 없음)
"""

import customtkinter as ctk
from ui.theme import AppTheme as T
from ui.components.sidebar import Sidebar
from ui.pages.dashboard_page import DashboardPage
from ui.pages.contact_page import ContactPage
from ui.pages.message_page import MessagePage
from ui.pages.send_page import SendPage
from ui.pages.settings_page import SettingsPage


class App(ctk.CTk):
    """로컬 전용 메인 애플리케이션"""

    def __init__(self, orchestrator=None):
        super().__init__()
        self.orchestrator = orchestrator

        self.title("TalkPC Local")
        self.geometry("1200x1000")
        self.minsize(1000, 850)
        self.configure(fg_color=T.BG_DARK)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 사이드바
        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        # 메인 콘텐츠
        self.content_frame = ctk.CTkFrame(self, fg_color=T.BG_DARK, corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # 페이지 생성
        self.pages = {}
        self.pages["dashboard"] = DashboardPage(
            self.content_frame, orchestrator=self.orchestrator
        )
        self.pages["contacts"] = ContactPage(
            self.content_frame, orchestrator=self.orchestrator
        )
        self.pages["message"] = MessagePage(
            self.content_frame, orchestrator=self.orchestrator
        )
        self.pages["send"] = SendPage(
            self.content_frame, orchestrator=self.orchestrator,
            message_page=self.pages["message"]
        )
        self.pages["settings"] = SettingsPage(
            self.content_frame, orchestrator=self.orchestrator
        )

        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        # 오케스트레이터 콜백
        if self.orchestrator:
            self.orchestrator.on_state_change(self._on_orch_state)
            self.orchestrator.on_log(self._on_orch_log)

        self._navigate("dashboard")
        self.after(500, self._auto_init)

        if self.orchestrator:
            self.orchestrator.scheduler.start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _navigate(self, page_id: str):
        if page_id in self.pages:
            self.pages[page_id].tkraise()
            self.sidebar.set_active(page_id)
            if page_id == "dashboard":
                self.pages["dashboard"].refresh_stats()
            elif page_id == "contacts":
                self.pages["contacts"].refresh_list()
            elif page_id == "send":
                self.pages["send"]._refresh_all()

    def _on_orch_state(self, state):
        def _update():
            state_map = {
                "idle": ("● 대기 중", T.TEXT_MUTED),
                "initializing": ("◌ 초기화 중...", T.WARNING),
                "ready": ("● 준비 완료", T.SUCCESS),
                "sending": ("◉ 발송 중...", T.ACCENT),
                "paused": ("◎ 일시정지", T.WARNING),
                "completed": ("✓ 발송 완료", T.SUCCESS),
                "error": ("✗ 오류", T.ERROR)
            }
            text, color = state_map.get(state, ("● 알 수 없음", T.TEXT_MUTED))
            self.sidebar.update_status(text, color)
        self.after(0, _update)

    def _on_orch_log(self, message, level):
        def _update():
            if "dashboard" in self.pages:
                self.pages["dashboard"].add_log(message, level)
        self.after(0, _update)

    def _auto_init(self):
        if "dashboard" in self.pages:
            self.pages["dashboard"].auto_initialize()

    def _on_close(self):
        if self.orchestrator:
            if self.orchestrator.state == "sending":
                self.orchestrator.stop_sending()
            self.orchestrator.scheduler.stop()
        self.destroy()
