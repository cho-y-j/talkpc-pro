"""
Custom Widgets - 재사용 가능한 커스텀 위젯
"""

import customtkinter as ctk
from ui.theme import AppTheme as T


class StatCard(ctk.CTkFrame):
    """통계 카드 위젯"""

    def __init__(self, parent, title: str, value: str, color: str = T.INFO, **kwargs):
        super().__init__(parent, corner_radius=T.CARD_RADIUS, **kwargs)
        self.configure(fg_color=T.BG_CARD, border_width=1, border_color=T.BORDER)

        self.title_label = ctk.CTkLabel(
            self, text=title,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_SECONDARY
        )
        self.title_label.pack(padx=T.CARD_PADDING, pady=(T.CARD_PADDING, 4), anchor="w")

        self.value_label = ctk.CTkLabel(
            self, text=value,
            font=(T.get_font_family(), 24, "bold"),
            text_color=color
        )
        self.value_label.pack(padx=T.CARD_PADDING, pady=(0, T.CARD_PADDING), anchor="w")

    def update_value(self, value: str, color: str = None):
        self.value_label.configure(text=value)
        if color:
            self.value_label.configure(text_color=color)


class LogPanel(ctk.CTkFrame):
    """실시간 로그 패널"""

    def __init__(self, parent, title: str = "로그", **kwargs):
        super().__init__(parent, corner_radius=T.CARD_RADIUS, **kwargs)
        self.configure(fg_color=T.BG_CARD, border_width=1, border_color=T.BORDER)

        # 헤더
        header = ctk.CTkFrame(self, fg_color="transparent", height=36)
        header.pack(fill="x", padx=T.CARD_PADDING, pady=(T.CARD_PADDING, 8))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text=title,
            font=(T.get_font_family(), T.FONT_SIZE_HEADER, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        self.clear_btn = ctk.CTkButton(
            header, text="지우기", width=60, height=26,
            font=(T.get_font_family(), T.FONT_SIZE_TINY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_SECONDARY,
            corner_radius=4,
            command=self.clear
        )
        self.clear_btn.pack(side="right")

        # 텍스트 영역
        self.textbox = ctk.CTkTextbox(
            self,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT,
            text_color=T.TEXT_SECONDARY,
            corner_radius=6,
            border_width=0,
            state="disabled"
        )
        self.textbox.pack(fill="both", expand=True, padx=T.CARD_PADDING, pady=(0, T.CARD_PADDING))

    def add_log(self, message: str, level: str = "info"):
        """로그 메시지 추가"""
        color_map = {
            "success": T.SUCCESS,
            "error": T.ERROR,
            "warning": T.WARNING,
            "info": T.TEXT_SECONDARY
        }

        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self):
        """로그 지우기"""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")


class ContactListItem(ctk.CTkFrame):
    """연락처 리스트 아이템"""

    def __init__(self, parent, name: str, category: str, phone: str = "",
                 selected: bool = False, on_select=None, **kwargs):
        super().__init__(parent, corner_radius=6, height=48, **kwargs)
        self.configure(fg_color=T.BG_INPUT if not selected else T.BG_HOVER)
        self.pack_propagate(False)

        self.name = name
        self.is_selected = selected
        self.on_select = on_select

        # 체크박스
        self.checkbox = ctk.CTkCheckBox(
            self, text="",
            width=20,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            border_color=T.BORDER,
            command=self._toggle
        )
        self.checkbox.pack(side="left", padx=(12, 8))

        if selected:
            self.checkbox.select()

        # 카테고리 뱃지
        cat_color = T.CATEGORY_COLORS.get(category, T.TEXT_MUTED)
        cat_badge = ctk.CTkLabel(
            self, text=f"  {category}  ",
            font=(T.get_font_family(), 9),
            fg_color=cat_color,
            text_color=T.BG_DARK,
            corner_radius=4
        )
        cat_badge.pack(side="left", padx=(0, 8))

        # 이름
        name_label = ctk.CTkLabel(
            self, text=name,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.TEXT_PRIMARY
        )
        name_label.pack(side="left", padx=(0, 8))

        # 전화번호
        if phone:
            phone_label = ctk.CTkLabel(
                self, text=phone,
                font=(T.get_font_family(), T.FONT_SIZE_SMALL),
                text_color=T.TEXT_MUTED
            )
            phone_label.pack(side="left")

    def _toggle(self):
        self.is_selected = self.checkbox.get()
        if self.on_select:
            self.on_select(self.name, self.is_selected)


class ProgressCard(ctk.CTkFrame):
    """발송 진행 상태 카드"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=T.CARD_RADIUS, **kwargs)
        self.configure(fg_color=T.BG_CARD, border_width=1, border_color=T.BORDER)

        # 현재 대상
        self.current_label = ctk.CTkLabel(
            self, text="대기 중...",
            font=(T.get_font_family(), T.FONT_SIZE_HEADER, "bold"),
            text_color=T.TEXT_PRIMARY
        )
        self.current_label.pack(padx=T.CARD_PADDING, pady=(T.CARD_PADDING, 8))

        # 프로그레스 바
        self.progress = ctk.CTkProgressBar(
            self, width=400,
            progress_color=T.ACCENT,
            fg_color=T.BG_INPUT,
            corner_radius=4
        )
        self.progress.pack(padx=T.CARD_PADDING, pady=4)
        self.progress.set(0)

        # 카운터
        self.count_label = ctk.CTkLabel(
            self, text="0 / 0",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY
        )
        self.count_label.pack(padx=T.CARD_PADDING, pady=(4, T.CARD_PADDING))

    def update_progress(self, current: int, total: int, name: str = ""):
        self.current_label.configure(text=f"📨 {name}" if name else "대기 중...")
        self.count_label.configure(text=f"{current} / {total}")
        self.progress.set(current / total if total > 0 else 0)

    def reset(self):
        self.current_label.configure(text="대기 중...")
        self.count_label.configure(text="0 / 0")
        self.progress.set(0)
