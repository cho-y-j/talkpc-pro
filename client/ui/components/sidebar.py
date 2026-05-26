"""
Sidebar - 로컬 전용 사이드바
"""

import customtkinter as ctk
from ui.theme import AppTheme as T


class Sidebar(ctk.CTkFrame):
    """좌측 사이드바 네비게이션"""

    def __init__(self, parent, on_navigate=None, on_logout=None, **kwargs):
        super().__init__(parent, width=T.SIDEBAR_WIDTH, corner_radius=0, **kwargs)
        self.configure(fg_color=T.BG_SIDEBAR)
        self.on_navigate = on_navigate
        self.on_logout = on_logout
        self.buttons = {}
        self.active_page = None

        self.grid_propagate(False)
        self._build()

    def _build(self):
        # 로고
        logo_frame = ctk.CTkFrame(self, fg_color="transparent", height=80)
        logo_frame.pack(fill="x", padx=16, pady=(20, 10))
        logo_frame.pack_propagate(False)

        ctk.CTkLabel(
            logo_frame, text="💬",
            font=(T.get_font_family(), 28), text_color=T.ACCENT
        ).pack(pady=(5, 0))

        ctk.CTkLabel(
            logo_frame, text="TalkPC Local",
            font=(T.get_font_family(), 13, "bold"), text_color=T.TEXT_PRIMARY
        ).pack()

        ctk.CTkLabel(
            logo_frame, text="카카오톡 자동 발송",
            font=(T.get_font_family(), 10), text_color=T.TEXT_SECONDARY
        ).pack()

        ctk.CTkFrame(self, fg_color=T.BORDER, height=1).pack(fill="x", padx=16, pady=10)

        # 메뉴
        menu_items = [
            ("dashboard", "📊  대시보드"),
            ("send", "🚀  발송"),
            ("contacts", "👥  연락처"),
            ("message", "✉  메시지 디자이너"),
            ("settings", "⚙️  설정"),
        ]

        for page_id, label in menu_items:
            btn = ctk.CTkButton(
                self, text=label, font=(T.get_font_family(), 13),
                anchor="w", height=42, corner_radius=8,
                fg_color="transparent", text_color=T.TEXT_SECONDARY,
                hover_color=T.BG_HOVER,
                command=lambda pid=page_id: self._on_click(pid)
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.buttons[page_id] = btn

        # 하단
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        ctk.CTkFrame(self, fg_color=T.BORDER, height=1).pack(fill="x", padx=16, pady=(0, 8))

        # 로그아웃
        ctk.CTkButton(
            self, text="🚪  로그아웃", font=(T.get_font_family(), 12),
            anchor="w", height=36, corner_radius=8,
            fg_color="transparent", text_color=T.TEXT_SECONDARY,
            hover_color=T.BG_HOVER,
            command=self._on_logout,
        ).pack(fill="x", padx=12, pady=(0, 6))

        self.status_label = ctk.CTkLabel(
            self, text="● 대기 중",
            font=(T.get_font_family(), 10), text_color=T.TEXT_MUTED
        )
        self.status_label.pack(padx=16, pady=(0, 5))

        ctk.CTkLabel(
            self, text="v1.1.0 Local",
            font=(T.get_font_family(), 9), text_color=T.TEXT_MUTED
        ).pack(padx=16, pady=(0, 16))

        self.set_active("dashboard")

    def _on_click(self, page_id: str):
        self.set_active(page_id)
        if self.on_navigate:
            self.on_navigate(page_id)

    def _on_logout(self):
        if self.on_logout:
            self.on_logout()

    def set_active(self, page_id: str):
        self.active_page = page_id
        for pid, btn in self.buttons.items():
            if pid == page_id:
                btn.configure(fg_color=T.ACCENT, text_color=T.TEXT_ON_ACCENT,
                              hover_color=T.ACCENT_HOVER)
            else:
                btn.configure(fg_color="transparent", text_color=T.TEXT_SECONDARY,
                              hover_color=T.BG_HOVER)

    def update_status(self, text: str, color: str = None):
        self.status_label.configure(text=text, text_color=color or T.TEXT_MUTED)
