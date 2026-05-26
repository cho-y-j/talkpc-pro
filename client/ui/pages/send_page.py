"""
Send Page - 발송 실행 페이지 (LOCAL-ONLY)
대상 선택 (Treeview 다중선택) + 메시지 작성 + 발송 실행
카카오톡 봇 전용 로컬 모드
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from tkinter import messagebox
from ui.theme import AppTheme as T
from ui.components.widgets import ProgressCard


class SendPage(ctk.CTkFrame):
    """발송 실행 페이지 - 대상 선택 + 메시지 + 발송 (카카오톡 봇 전용)"""

    def __init__(self, parent, orchestrator=None, message_page=None, **kwargs):
        super().__init__(parent, fg_color=T.BG_DARK, **kwargs)
        self.orchestrator = orchestrator
        self.message_page = message_page
        self.selected_ids = set()  # 선택된 연락처 ID
        self.contact_checkboxes = {}  # {contact_id: checkbox}
        self._selected_template = None  # 선택된 템플릿 (변형 랜덤용)
        self._build()

    def _build(self):
        # -- 헤더 --
        header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        header.pack(fill="x", padx=24, pady=(20, 8))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="🚀 메시지 발송",
            font=(T.get_font_family(), T.FONT_SIZE_TITLE, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        # 카톡 친구탭 OCR 기반 오늘 생일자 즉시 발송
        ctk.CTkButton(
            header, text="🎂 생일자 즉시발송", width=140,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            fg_color="#e67e22", hover_color="#d35400",
            text_color="white", height=32, corner_radius=6,
            command=self._send_kakao_birthday
        ).pack(side="right")

        # 매일 생일자 자동발송 설정 (스케줄러 auto_send_settings 직접 편집)
        ctk.CTkButton(
            header, text="📅 매일 생일자 자동", width=130,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color="#8e44ad", hover_color="#7d3c98",
            text_color="white", height=32, corner_radius=6,
            command=self._open_birthday_schedule_dialog
        ).pack(side="right", padx=(0, 6))

        # -- 발송 방법 (카카오톡 봇 전용) --
        self.send_method_var = ctk.StringVar(value="카카오톡 봇")
        self._selected_method_key = "카카오톡 봇"

        method_frame = ctk.CTkFrame(self, fg_color="transparent", height=72)
        method_frame.pack(fill="x", padx=24, pady=(0, 4))
        method_frame.pack_propagate(False)

        self._method_cards = {}
        card_btn = ctk.CTkButton(
            method_frame, text="💬\n카카오톡 봇\n무료",
            width=140, height=60,
            font=(T.get_font_family(), 10, "bold"),
            fg_color=T.BG_HOVER, hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
            border_width=2,
            border_color="#2ea043",
            corner_radius=10,
            command=lambda: None
        )
        card_btn.pack(side="left", padx=(0, 8))
        self._method_cards["카카오톡 봇"] = (card_btn, "#2ea043")

        # 발송 방법 상태 바
        self.method_status_label = ctk.CTkLabel(
            self, text="📨 카카오톡 봇으로 메시지 보내기 (무료)",
            font=(T.get_font_family(), 11, "bold"),
            text_color=T.TEXT_SECONDARY,
            fg_color=T.BG_CARD, corner_radius=6, height=28
        )
        self.method_status_label.pack(fill="x", padx=24, pady=(0, 4))

        # 권장 발송 시간대 안내 (차단 회피용 가이드 — 강제 X)
        ctk.CTkLabel(
            self,
            text="💡 권장 발송 시간: 09:00 ~ 22:00  ·  심야 시간대 발송은 봇 의심도가 높아질 수 있어요",
            font=(T.get_font_family(), 10),
            text_color="#f0b90b",
            fg_color="#3a2818", corner_radius=6, height=24,
        ).pack(fill="x", padx=24, pady=(0, 8))

        # -- 상단: 대상 선택 (좌) + 메시지 작성 (우) --
        top_frame = ctk.CTkFrame(self, fg_color="transparent", height=350)
        top_frame.pack(fill="both", padx=24, pady=(0, 8))
        top_frame.pack_propagate(False)
        top_frame.grid_columnconfigure(0, weight=2)
        top_frame.grid_columnconfigure(1, weight=3)
        top_frame.grid_rowconfigure(0, weight=1)

        # ═══ 좌측: 대상 선택 ═══
        left_card = ctk.CTkFrame(top_frame, fg_color=T.BG_CARD,
                                  corner_radius=T.CARD_RADIUS,
                                  border_width=1, border_color=T.BORDER)
        left_card.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        # 제목
        left_header = ctk.CTkFrame(left_card, fg_color="transparent", height=36)
        left_header.pack(fill="x", padx=12, pady=(12, 8))
        left_header.pack_propagate(False)

        ctk.CTkLabel(
            left_header, text="👥 발송 대상",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        self.selected_count_label = ctk.CTkLabel(
            left_header, text="0명 선택",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            text_color=T.ACCENT
        )
        self.selected_count_label.pack(side="right")

        # 검색
        self.contact_search = ctk.CTkEntry(
            left_card, placeholder_text="🔍 이름, 회사, 메모 검색...",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=32, corner_radius=6
        )
        self.contact_search.pack(fill="x", padx=12, pady=(0, 6))
        self.contact_search.bind("<KeyRelease>", lambda e: self._refresh_contact_list())

        # ── 필터 한 줄: 카테고리 + 발송기준 (OptionMenu 통합) ──
        # 발송기준 옵션 (라벨 = 변수값 — 별도 ID 매핑 불필요)
        self.SEND_FILTERS = [
            "전체",
            "한 번도 발송 안함",
            "최근 1일 미발송",
            "최근 3일 미발송",
            "최근 7일 미발송",
            "최근 14일 미발송",
            "최근 30일 미발송",
        ]

        filter_row = ctk.CTkFrame(left_card, fg_color="transparent", height=40)
        filter_row.pack(fill="x", padx=12, pady=(0, 4))
        filter_row.pack_propagate(False)

        ctk.CTkLabel(
            filter_row, text="카테고리",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 4))

        # 카테고리는 라벨↔ID 매핑 (한국어 표시, 내부 ID 별개)
        self._cat_label_to_id = {"전체": "all"}
        self._cat_id_to_label = {"all": "전체"}
        self.cat_filter_var = ctk.StringVar(value="전체")
        self.cat_option = ctk.CTkOptionMenu(
            filter_row, values=["전체"], variable=self.cat_filter_var,
            width=100, height=28,
            font=(T.get_font_family(), 11),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, dropdown_font=(T.get_font_family(), 11),
            command=lambda v: self._on_cat_filter_changed(v)
        )
        self.cat_option.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            filter_row, text="발송기준",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 4))

        self.send_filter_var = ctk.StringVar(value=self.SEND_FILTERS[0])
        self.send_filter_option = ctk.CTkOptionMenu(
            filter_row, values=self.SEND_FILTERS,
            variable=self.send_filter_var,
            width=170, height=28,
            font=(T.get_font_family(), 11),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, dropdown_font=(T.get_font_family(), 11),
            command=lambda v: self._refresh_contact_list()
        )
        self.send_filter_option.pack(side="left")

        # ── 선택/해제 + 필터 카운트 ──
        select_frame = ctk.CTkFrame(left_card, fg_color="transparent", height=32)
        select_frame.pack(fill="x", padx=12, pady=(0, 4))
        select_frame.pack_propagate(False)

        ctk.CTkButton(
            select_frame, text="전체 선택", width=80, height=26,
            font=(T.get_font_family(), 11),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_SECONDARY, corner_radius=4,
            command=self._select_all
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            select_frame, text="전체 해제", width=80, height=26,
            font=(T.get_font_family(), 11),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_SECONDARY, corner_radius=4,
            command=self._deselect_all
        ).pack(side="left")

        # 필터 결과 카운트
        self.filter_count_label = ctk.CTkLabel(
            select_frame, text="",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_MUTED
        )
        self.filter_count_label.pack(side="right")

        # Treeview 스타일
        style = ttk.Style()
        style.configure("Send.Treeview",
                         background="#1c2333", foreground="#e6edf3",
                         fieldbackground="#1c2333", borderwidth=0,
                         font=(T.get_font_family(), 11), rowheight=30)
        style.configure("Send.Treeview.Heading",
                         background="#2d333b", foreground="#e6edf3",
                         font=(T.get_font_family(), 11, "bold"), borderwidth=0)
        style.map("Send.Treeview",
                   background=[("selected", "#2f81f7")],
                   foreground=[("selected", "#ffffff")])

        # 연락처 Treeview (순번 + 체크 + 이름 + 그룹 + 발송횟수 + 마지막발송)
        tree_frame = tk.Frame(left_card, bg="#1c2333")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        send_cols = ("no", "check", "name", "category", "sent_count", "last_sent")
        self.send_tree = ttk.Treeview(
            tree_frame, columns=send_cols, show="headings",
            selectmode="none", style="Send.Treeview"
        )
        self.send_tree.heading("no", text="#", anchor="center")
        self.send_tree.heading("check", text="V", anchor="center")
        self.send_tree.heading("name", text="이름", anchor="w")
        self.send_tree.heading("category", text="그룹", anchor="w")
        self.send_tree.heading("sent_count", text="발송", anchor="center")
        self.send_tree.heading("last_sent", text="마지막 발송", anchor="w")
        self.send_tree.column("no", width=35, minwidth=30, stretch=False, anchor="center")
        self.send_tree.column("check", width=28, minwidth=28, stretch=False)
        self.send_tree.column("name", width=80, minwidth=60)
        self.send_tree.column("category", width=50, minwidth=40)
        self.send_tree.column("sent_count", width=40, minwidth=35, anchor="center")
        self.send_tree.column("last_sent", width=110, minwidth=90)

        # 태그: 체크 상태 + 발송 상태
        self.send_tree.tag_configure("checked", background="#1a3a2a", foreground="#3fb950")
        self.send_tree.tag_configure("unchecked", background="#1c2333", foreground="#e6edf3")
        self.send_tree.tag_configure("sent_today", background="#1c2333", foreground="#8b949e")  # 오늘 발송 = 회색

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.send_tree.yview)
        self.send_tree.configure(yscrollcommand=sb.set)
        self.send_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # 클릭 → 체크 토글
        self.send_tree.bind("<Button-1>", self._on_tree_click_toggle)
        self._send_tree_id_map = {}  # iid → contact_id

        # ═══ 우측: 메시지 작성 ═══
        right_card = ctk.CTkFrame(top_frame, fg_color=T.BG_CARD,
                                   corner_radius=T.CARD_RADIUS,
                                   border_width=1, border_color=T.BORDER)
        right_card.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

        # 제목
        right_header = ctk.CTkFrame(right_card, fg_color="transparent", height=36)
        right_header.pack(fill="x", padx=12, pady=(12, 8))
        right_header.pack_propagate(False)

        ctk.CTkLabel(
            right_header, text="💬 메시지",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        # 템플릿 불러오기
        tmpl_frame = ctk.CTkFrame(right_card, fg_color="transparent", height=32)
        tmpl_frame.pack(fill="x", padx=12, pady=(0, 6))
        tmpl_frame.pack_propagate(False)

        ctk.CTkLabel(
            tmpl_frame, text="템플릿:",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        ).pack(side="left", padx=(0, 4))

        self.template_var = ctk.StringVar(value="직접 입력")
        self.template_menu = ctk.CTkOptionMenu(
            tmpl_frame, values=["직접 입력"],
            variable=self.template_var,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, height=28, corner_radius=4,
            command=self._on_template_select
        )
        self.template_menu.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            tmpl_frame, text="🔄", width=28, height=28,
            font=(T.get_font_family(), 12),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_SECONDARY, corner_radius=4,
            command=self._refresh_templates
        ).pack(side="right")

        # 템플릿 미리보기 스니펫 (항상 존재, 텍스트 비면 높이 0)
        self._tmpl_preview_frame = ctk.CTkFrame(right_card, fg_color="transparent", height=0)
        self._tmpl_preview_frame.pack(fill="x", padx=12, pady=0)
        self._tmpl_preview_frame.pack_propagate(False)

        self.template_preview_label = ctk.CTkLabel(
            self._tmpl_preview_frame, text="",
            font=(T.get_font_family(), 9),
            text_color=T.TEXT_MUTED, anchor="w",
            fg_color=T.BG_INPUT, corner_radius=4, height=20
        )
        self.template_preview_label.pack(fill="x")

        # 변수 버튼들
        var_frame = ctk.CTkFrame(right_card, fg_color="transparent", height=28)
        var_frame.pack(fill="x", padx=12, pady=(0, 4))
        var_frame.pack_propagate(False)

        ctk.CTkLabel(
            var_frame, text="변수:",
            font=(T.get_font_family(), 9),
            text_color=T.TEXT_MUTED
        ).pack(side="left", padx=(0, 4))

        for var in ["%이름%", "%카테고리%", "%회사%", "%직급%", "%생일%", "%기념일%", "%날짜%", "%요일%"]:
            ctk.CTkButton(
                var_frame, text=var, width=50, height=22,
                font=(T.get_font_family(), 9),
                fg_color=T.BG_HOVER, hover_color=T.BORDER,
                text_color=T.INFO, corner_radius=4,
                command=lambda v=var: self.msg_editor.insert("insert", v)
            ).pack(side="left", padx=1)

        # 메시지 에디터
        self.msg_editor = ctk.CTkTextbox(
            right_card,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, text_color=T.TEXT_PRIMARY,
            corner_radius=6, border_width=1, border_color=T.BORDER
        )
        self.msg_editor.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.msg_editor.insert("1.0", "안녕하세요 %이름%님!\n\n")

        # 이미지 첨부
        img_frame = ctk.CTkFrame(right_card, fg_color="transparent", height=28)
        img_frame.pack(fill="x", padx=12, pady=(0, 4))
        img_frame.pack_propagate(False)

        self.image_path = None

        ctk.CTkButton(
            img_frame, text="📎 이미지 첨부", width=100, height=24,
            font=(T.get_font_family(), 9),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=4,
            command=self._select_image
        ).pack(side="left", padx=(0, 4))

        self.image_label = ctk.CTkLabel(
            img_frame, text="첨부 없음",
            font=(T.get_font_family(), 9),
            text_color=T.TEXT_MUTED
        )
        self.image_label.pack(side="left", padx=(0, 4))

        self.image_clear_btn = ctk.CTkButton(
            img_frame, text="✕", width=22, height=22,
            font=(T.get_font_family(), 10),
            fg_color="transparent", hover_color=T.ERROR,
            text_color=T.TEXT_MUTED, corner_radius=4,
            command=self._clear_image
        )

        # 미리보기
        preview_header = ctk.CTkFrame(right_card, fg_color="transparent", height=22)
        preview_header.pack(fill="x", padx=12)
        preview_header.pack_propagate(False)

        ctk.CTkLabel(
            preview_header, text="👁 미리보기",
            font=(T.get_font_family(), 9, "bold"),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left")

        ctk.CTkButton(
            preview_header, text="새로고침", width=60, height=18,
            font=(T.get_font_family(), 9),
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.TEXT_MUTED, corner_radius=4,
            command=self._update_preview
        ).pack(side="right")

        self.preview_box = ctk.CTkTextbox(
            right_card, height=70,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, text_color=T.SUCCESS,
            corner_radius=6, state="disabled"
        )
        self.preview_box.pack(fill="x", padx=12, pady=(2, 12))

        # -- 하단: 컨트롤 + 로그 --
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        # 컨트롤 바 - Row 1: 메인 버튼들
        control_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent", height=50)
        control_frame.pack(fill="x", pady=(0, 4))
        control_frame.pack_propagate(False)

        self.start_btn = ctk.CTkButton(
            control_frame, text="▶  발송 시작", width=130,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            fg_color="#2ea043", hover_color="#3fb950",
            text_color="#ffffff", height=42, corner_radius=8,
            command=self._start_send
        )
        self.start_btn.pack(side="left", padx=(0, 4))

        self.pause_btn = ctk.CTkButton(
            control_frame, text="⏸  일시정지", width=100,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color="#b08800", hover_color="#d29922",
            text_color="#ffffff", height=42, corner_radius=8,
            command=self._pause_send
        )
        self.pause_btn.pack(side="left", padx=(0, 4))

        self.stop_btn = ctk.CTkButton(
            control_frame, text="⏹  중지", width=80,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color="#b62324", hover_color="#f85149",
            text_color="#ffffff", height=42, corner_radius=8,
            command=self._stop_send
        )
        self.stop_btn.pack(side="left", padx=(0, 4))

        self.schedule_btn = ctk.CTkButton(
            control_frame, text="⏰ 예약", width=80,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color="#2471a3", hover_color="#3498db",
            text_color="#ffffff", height=42, corner_radius=8,
            command=self._schedule_send
        )
        self.schedule_btn.pack(side="left", padx=(0, 4))

        # 실패 재발송 — 직전 발송에서 실패한 건만 큐로 다시 로드
        self.retry_btn = ctk.CTkButton(
            control_frame, text="↻ 실패 재발송", width=120,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color="#b62324", hover_color="#f85149",
            text_color="#ffffff", height=42, corner_radius=8,
            command=self._retry_failed
        )
        self.retry_btn.pack(side="left", padx=(0, 8))

        # 딜레이 설정
        ctk.CTkLabel(
            control_frame, text="간격:",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        ).pack(side="left", padx=(0, 2))

        self.delay_min = ctk.CTkEntry(
            control_frame, width=40, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=4
        )
        self.delay_min.pack(side="left", padx=(0, 2))
        self.delay_min.insert(0, "5")

        ctk.CTkLabel(
            control_frame, text="~",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        ).pack(side="left", padx=2)

        self.delay_max = ctk.CTkEntry(
            control_frame, width=40, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=4
        )
        self.delay_max.pack(side="left", padx=(0, 2))
        self.delay_max.insert(0, "15")

        ctk.CTkLabel(
            control_frame, text="초",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        ).pack(side="left")

        # 진행 바
        self.progress_card = ProgressCard(control_frame)
        self.progress_card.pack(side="right")

        # 로그 (크게!)
        log_card = ctk.CTkFrame(bottom_frame, fg_color=T.BG_CARD,
                                 corner_radius=T.CARD_RADIUS,
                                 border_width=1, border_color=T.BORDER)
        log_card.pack(fill="both", expand=True)

        log_header = ctk.CTkFrame(log_card, fg_color="transparent", height=32)
        log_header.pack(fill="x", padx=12, pady=(8, 4))
        log_header.pack_propagate(False)

        ctk.CTkLabel(
            log_header, text="발송 로그",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        ctk.CTkButton(
            log_header, text="지우기", width=50, height=24,
            font=(T.get_font_family(), T.FONT_SIZE_TINY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_SECONDARY, corner_radius=4,
            command=self._clear_log
        ).pack(side="right")

        self.log_textbox = ctk.CTkTextbox(
            log_card,
            font=(T.get_font_family(), 12),
            fg_color=T.BG_INPUT,
            text_color=T.TEXT_SECONDARY,
            corner_radius=6,
            border_width=0,
            state="disabled"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # 로그 색상 태그
        self.log_textbox._textbox.tag_configure("success", foreground=T.SUCCESS)
        self.log_textbox._textbox.tag_configure("error", foreground=T.ERROR)
        self.log_textbox._textbox.tag_configure("warning", foreground=T.WARNING)
        self.log_textbox._textbox.tag_configure("info", foreground=T.TEXT_SECONDARY)

        # LogPanel 호환 객체 생성 (외부에서 self.log_panel.add_log 호출용)
        self.log_panel = self

        # 초기 로드
        self._refresh_all()

    # ═══ 로그 메서드 (LogPanel 호환) ═══

    def add_log(self, message: str, level: str = "info"):
        """로그 추가 (색상 + 타임스탬프)"""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.configure(state="normal")
        self.log_textbox._textbox.insert("end", f"[{ts}] {message}\n", level)
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def _clear_log(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    # ═══ 이미지 첨부 ═══

    def _select_image(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="이미지 선택",
            filetypes=[("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if filepath:
            self.image_path = filepath
            filename = filepath.split("/")[-1].split("\\")[-1]
            self.image_label.configure(text=filename, text_color=T.ACCENT)
            self.image_clear_btn.pack(side="left")

    def _clear_image(self):
        self.image_path = None
        self.image_label.configure(text="첨부 없음", text_color=T.TEXT_MUTED)
        self.image_clear_btn.pack_forget()

    # ═══ 연락처 리스트 ═══

    def _refresh_all(self):
        """전체 새로고침"""
        self._refresh_category_filter()
        self._refresh_contact_list()
        self._refresh_templates()

    def _refresh_category_filter(self):
        """카테고리 OptionMenu values 갱신 (라벨↔ID 매핑 재구축)"""
        labels = ["전체"]
        self._cat_label_to_id = {"전체": "all"}
        self._cat_id_to_label = {"all": "전체"}

        if self.orchestrator:
            cat_name_map = {"friend": "친구", "family": "가족", "business": "사업체",
                            "vip": "VIP", "other": "기타", "kakao_friend": "카카오"}
            for cat in self.orchestrator.contact_mgr.get_all_categories():
                label = cat_name_map.get(cat, cat)
                # 라벨 충돌 방지 — 동일 라벨이 이미 있으면 ID 그대로 사용
                if label in self._cat_label_to_id:
                    label = cat
                labels.append(label)
                self._cat_label_to_id[label] = cat
                self._cat_id_to_label[cat] = label

        self.cat_option.configure(values=labels)
        # 현재 선택값이 사라졌으면 "전체"로
        if self.cat_filter_var.get() not in labels:
            self.cat_filter_var.set("전체")

    def _on_cat_filter_changed(self, _label):
        """카테고리 OptionMenu 변경 콜백"""
        self._refresh_contact_list()

    def _refresh_contact_list(self):
        """연락처 Treeview 갱신 (체크 + 이름 + 그룹 + 발송횟수 + 마지막발송)"""
        for item in self.send_tree.get_children():
            self.send_tree.delete(item)
        self._send_tree_id_map.clear()

        search = self.contact_search.get().strip().lower()
        # 카테고리: 라벨 → ID 변환 (드롭다운 표시값은 한국어, 내부 비교는 ID)
        cat_label = self.cat_filter_var.get()
        category = self._cat_label_to_id.get(cat_label, "all")
        send_filter = self.send_filter_var.get()  # 한국어 라벨 = 분기 키

        from datetime import datetime, timedelta

        cat_label_map = {
            "friend": "친구", "family": "가족", "business": "사업체",
            "vip": "VIP", "other": "기타", "미지정": "미지정",
            "kakao_friend": "카카오"
        }
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        if self.orchestrator:
            contacts = self.orchestrator.contact_mgr.get_by_category(category)

            # 발송 상태 필터
            if send_filter == "한 번도 발송 안함":
                contacts = [c for c in contacts if not c.last_sent]
            elif send_filter.startswith("최근 ") and send_filter.endswith("일 미발송"):
                # "최근 N일 미발송" — N일 안에 발송 기록 없음
                try:
                    days = int(send_filter.replace("최근 ", "").replace("일 미발송", ""))
                    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
                    contacts = [c for c in contacts
                                if not c.last_sent or c.last_sent < cutoff]
                except ValueError:
                    pass
            # else "전체" — 필터 없음

            # 텍스트 검색
            if search:
                contacts = [
                    c for c in contacts
                    if search in c.name.lower()
                    or search in c.company.lower()
                    or search in c.memo.lower()
                    or search in c.category.lower()
                ]

            for idx, contact in enumerate(reversed(contacts), 1):
                is_checked = contact.id in self.selected_ids
                check_mark = "V" if is_checked else ""
                cat_text = cat_label_map.get(contact.category, contact.category)

                # 발송 횟수
                sent_count = str(contact.send_count) if contact.send_count > 0 else "-"

                # 마지막 발송 시간
                last_sent_text = ""
                is_sent_today = False
                if contact.last_sent:
                    try:
                        dt = datetime.fromisoformat(contact.last_sent)
                        if contact.last_sent.startswith(today):
                            last_sent_text = f"오늘 {dt.strftime('%H:%M')}"
                            is_sent_today = True
                        elif contact.last_sent.startswith(yesterday):
                            last_sent_text = f"어제 {dt.strftime('%H:%M')}"
                        else:
                            last_sent_text = dt.strftime("%m/%d %H:%M")
                    except Exception:
                        last_sent_text = contact.last_sent[:16]

                # 태그: 체크 > 오늘발송 > 기본
                if is_checked:
                    tag = "checked"
                elif is_sent_today:
                    tag = "sent_today"
                else:
                    tag = "unchecked"

                iid = self.send_tree.insert("", "end", values=(
                    idx, check_mark, contact.name, cat_text, sent_count, last_sent_text
                ), tags=(tag,))

                self._send_tree_id_map[iid] = contact.id

            # 필터 결과 카운트
            total_all = len(self.orchestrator.contact_mgr.get_by_category(category))
            shown = len(contacts)
            self.filter_count_label.configure(text=f"{shown}/{total_all}명")

        self._update_selected_count()

    def _on_tree_click_toggle(self, event):
        """Treeview 행 클릭 → 체크 토글"""
        iid = self.send_tree.identify_row(event.y)
        if not iid:
            return
        cid = self._send_tree_id_map.get(iid)
        if not cid:
            return
        # 토글
        if cid in self.selected_ids:
            self.selected_ids.discard(cid)
            self.send_tree.set(iid, "check", "")
            self.send_tree.item(iid, tags=("unchecked",))
        else:
            self.selected_ids.add(cid)
            self.send_tree.set(iid, "check", "V")
            self.send_tree.item(iid, tags=("checked",))
        self._update_selected_count()

    def _select_all(self):
        """현재 보이는 목록 전체 선택"""
        for iid in self.send_tree.get_children():
            cid = self._send_tree_id_map.get(iid)
            if cid:
                self.selected_ids.add(cid)
            self.send_tree.set(iid, "check", "V")
            self.send_tree.item(iid, tags=("checked",))
        self._update_selected_count()

    def _deselect_all(self):
        """전체 해제"""
        for iid in self.send_tree.get_children():
            self.send_tree.set(iid, "check", "")
            self.send_tree.item(iid, tags=("unchecked",))
        self.selected_ids.clear()
        self._update_selected_count()

    def _update_selected_count(self):
        total = len(self.send_tree.get_children())
        selected = len(self.selected_ids)
        self.selected_count_label.configure(text=f"{selected}명 선택 / {total}명")

    # ═══ 메시지 / 템플릿 ═══

    def _refresh_templates(self):
        """템플릿 드롭다운 갱신"""
        names = ["직접 입력"]
        self._template_map = {}
        if self.orchestrator:
            for tmpl in self.orchestrator.message_engine.get_templates():
                label = tmpl.name
                if len(tmpl.contents) > 1:
                    label += f" ({len(tmpl.contents)}변형)"
                names.append(label)
                self._template_map[label] = tmpl
        self.template_menu.configure(values=names)

    def _on_template_select(self, name):
        if name == "직접 입력":
            self._selected_template = None
            self._tmpl_preview_frame.configure(height=0)
            self.template_preview_label.configure(text="")
            return
        tmpl = self._template_map.get(name)
        if tmpl:
            # 미리보기 스니펫 표시
            snippet = tmpl.content.replace("\n", " ")[:50]
            if len(tmpl.content) > 50:
                snippet += "..."
            self.template_preview_label.configure(text=f"  📄 {snippet}")
            self._tmpl_preview_frame.configure(height=24)
            self._selected_template = tmpl
            self.msg_editor.delete("1.0", "end")
            self.msg_editor.insert("1.0", tmpl.content)
            # 변형 개수 표시
            if len(tmpl.contents) > 1:
                self.log_panel.add_log(
                    f"템플릿 '{name}': {len(tmpl.contents)}개 변형 → 랜덤 발송",
                    "info"
                )
            # 템플릿에 이미지가 첨부되어 있으면 자동 로드
            if tmpl.image_path:
                import os
                self.image_path = tmpl.image_path
                filename = os.path.basename(tmpl.image_path)
                self.image_label.configure(text=filename, text_color=T.ACCENT)
                self.image_clear_btn.pack(side="left")
            self._update_preview()

    def _update_preview(self):
        content = self.msg_editor.get("1.0", "end").strip()
        if not content:
            return

        preview = content
        if self.orchestrator:
            contacts = self.orchestrator.contact_mgr.get_all()
            if contacts:
                preview = self.orchestrator.message_engine.substitute(
                    content, contacts[0].to_dict()
                )
            else:
                sample = {"name": "홍길동", "company": "ABC회사", "position": "대리"}
                preview = self.orchestrator.message_engine.substitute(content, sample)

        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", preview)
        self.preview_box.configure(state="disabled")

    def get_current_message(self) -> str:
        return self.msg_editor.get("1.0", "end").strip()

    # ═══ 발송 ═══

    def _start_send(self):
        # 디버그 로그
        if hasattr(self, 'log_panel'):
            self.log_panel.add_log(
                f"발송 시작 → 카카오톡 봇, 선택: {len(self.selected_ids)}명",
                "info"
            )
        # 선택 확인
        if not self.selected_ids:
            messagebox.showwarning("발송 불가", "발송 대상을 선택해주세요.")
            return

        message = self.get_current_message()
        if not message:
            messagebox.showwarning("발송 불가", "메시지를 입력해주세요.")
            return

        if not self.orchestrator:
            self.log_panel.add_log("orchestrator 없음", "error")
            return

        # sender가 없으면 자동 초기화 (학습 좌표 OR 디폴트 좌표)
        if not self.orchestrator.sender:
            self.add_log("자동 초기화 중...", "info")

            if not self.orchestrator.window_ctrl.find_kakao_window():
                messagebox.showwarning("발송 불가", "카카오톡이 실행되어 있지 않습니다.")
                return

            # 좌표: 학습 파일 있으면 사용, 없으면 디폴트 자동 계산
            if not self.orchestrator.coordinates:
                from pathlib import Path
                positions_path = self.orchestrator.base_dir / "config" / "learned_positions.json"
                if positions_path.exists():
                    import json
                    with open(positions_path, "r", encoding="utf-8") as f:
                        self.orchestrator.coordinates = json.load(f)
                else:
                    coords = self.orchestrator.window_ctrl.calculate_ui_coordinates()
                    self.orchestrator.coordinates = coords

            self.orchestrator.confirm_calibration()
            if not self.orchestrator.sender:
                messagebox.showwarning("발송 불가", "초기화 실패. 대시보드에서 초기화 버튼을 눌러주세요.")
                return
            self.add_log("초기화 완료!", "success")

        # sender 있으면 정상 진행 - 연락처 가져오기 (화면 표시 순서 = 최신순)
        selected_contacts = [
            c for c in reversed(self.orchestrator.contact_mgr.get_all())
            if c.id in self.selected_ids
        ]
        if not selected_contacts:
            messagebox.showwarning("발송 불가", "선택된 연락처가 없습니다.")
            return

        tmpl = getattr(self, '_selected_template', None)
        template_contents = None
        if tmpl and len(tmpl.contents) > 1:
            template_contents = tmpl.contents

        self.log_panel.add_log(f"큐 준비: {len(selected_contacts)}명, 메시지: {message[:30]}...", "info")
        try:
            self.orchestrator.prepare_custom_queue(
                selected_contacts, message,
                image_path=self.image_path,
                template_contents=template_contents
            )
        except Exception as e:
            self.log_panel.add_log(f"큐 준비 오류: {e}", "error")
            return

        variation_info = f" ({len(template_contents)}개 변형 랜덤)" if template_contents else ""
        self.log_panel.add_log(f"[카카오톡 봇] 발송 큐: {len(self.orchestrator.send_queue)}건{variation_info}", "info")

        self.orchestrator.on_progress(self._on_progress)
        self.orchestrator.on_result(self._on_result)
        self.orchestrator.on_log(self._on_log)
        self.orchestrator.on_state_change(self._on_state_change)
        self.start_btn.configure(state="disabled")

        self.log_panel.add_log(f"카카오봇 발송 시작 (sender={self.orchestrator.sender is not None})", "info")
        try:
            d_min = int(self.delay_min.get())
            d_max = int(self.delay_max.get())
            self.orchestrator.sender.delay_min = d_min
            self.orchestrator.sender.delay_max = d_max
        except ValueError:
            pass
        self.orchestrator.start_sending()

    def _start_unsent_only(self):
        """미발송자만 발송 (오늘 안 보낸 사람만)"""
        if not self.orchestrator:
            return

        message = self.get_current_message()
        if not message:
            messagebox.showwarning("발송 불가", "메시지를 입력해주세요.")
            return

        # sender 없으면 자동 초기화
        if not self.orchestrator.sender:
            self.add_log("카카오톡 초기화 필요 - 먼저 초기화 후 다시 시도하세요.", "warning")
            return

        # 라벨 → ID 변환 (드롭다운 표시값과 내부 ID 분리)
        cat_label = self.cat_filter_var.get()
        category = self._cat_label_to_id.get(cat_label, "all")
        tmpl = getattr(self, '_selected_template', None)
        template_contents = None
        if tmpl and len(tmpl.contents) > 1:
            template_contents = tmpl.contents

        queue_info = self.orchestrator.prepare_unsent_queue(
            category, message,
            image_path=self.image_path,
            template_contents=template_contents
        )

        if not queue_info:
            messagebox.showinfo("발송 완료", "오늘 미발송자가 없습니다. 모두 발송 완료!")
            return

        self.add_log(f"미발송자 {len(queue_info)}명 큐 준비 완료", "info")
        for item in queue_info[:5]:
            sent_info = f" (총 {item['send_count']}회)" if item['send_count'] > 0 else " (신규)"
            self.add_log(f"  - {item['name']}{sent_info}", "info")
        if len(queue_info) > 5:
            self.add_log(f"  ... 외 {len(queue_info) - 5}명", "info")

        self.orchestrator.on_progress(self._on_progress)
        self.orchestrator.on_result(self._on_result)
        self.orchestrator.on_log(self._on_log)
        self.orchestrator.on_state_change(self._on_state_change)
        self.start_btn.configure(state="disabled")

        try:
            d_min = int(self.delay_min.get())
            d_max = int(self.delay_max.get())
            self.orchestrator.sender.delay_min = d_min
            self.orchestrator.sender.delay_max = d_max
        except ValueError:
            pass
        self.orchestrator.start_sending()

    def _pause_send(self):
        if not self.orchestrator:
            return
        if self.orchestrator.state == "sending":
            self.orchestrator.pause_sending()
            self.pause_btn.configure(
                text="▶  재개",
                fg_color="#2ea043", hover_color="#3fb950"
            )
        elif self.orchestrator.state == "paused":
            self.orchestrator.resume_sending()
            self.pause_btn.configure(
                text="⏸  일시정지",
                fg_color="#b08800", hover_color="#d29922"
            )

    def _stop_send(self):
        if not self.orchestrator:
            return
        if self.orchestrator.state not in ("sending", "paused"):
            return
        if messagebox.askyesno("발송 중지", "정말 발송을 중지하시겠습니까?"):
            self.orchestrator.stop_sending()
            self.pause_btn.configure(
                text="⏸  일시정지",
                fg_color="#b08800", hover_color="#d29922"
            )
            self.log_panel.add_log("중지됨. 다시 시작할 수 있습니다.", "info")

    def _retry_failed(self):
        """직전 발송에서 실패한 건만 큐로 다시 로드 → 발송 시작 누르면 재시도."""
        if not self.orchestrator:
            return
        count = self.orchestrator.retry_failed()
        if count and count > 0:
            self.log_panel.add_log(
                f"실패 {count}건 재발송 큐 로드 완료. '▶ 발송 시작' 누르세요.",
                "info"
            )
        else:
            self.log_panel.add_log("재발송할 실패 건이 없습니다.", "warning")

    def _schedule_send(self):
        """예약 발송 다이얼로그"""
        if not self.orchestrator:
            return

        if not self.selected_ids:
            messagebox.showwarning("예약 불가", "발송 대상을 선택해주세요.")
            return

        message = self.get_current_message()
        if not message:
            messagebox.showwarning("예약 불가", "메시지를 입력해주세요.")
            return

        dialog = ScheduleDialog(self)
        self.wait_window(dialog)

        if dialog.result:
            recurring = getattr(dialog, "recurring", "none")
            job = self.orchestrator.scheduler.add_job(
                scheduled_time=dialog.result,
                contact_ids=list(self.selected_ids),
                template_content=message,
                image_path=self.image_path,
                recurring=recurring,
            )
            recur_label = " (매일 반복)" if recurring == "daily" else ""
            self.log_panel.add_log(
                f"예약 등록 완료: {job.display_time}{recur_label} "
                f"({len(self.selected_ids)}명)",
                "success"
            )

    # -- 콜백 (스레드 → 메인 스레드) --

    def _on_progress(self, current, total, name):
        self.after(0, lambda: self.progress_card.update_progress(current, total, name))

    def _on_result(self, result):
        def _update():
            emoji = "✅" if result["status"] == "success" else "❌"
            self.log_panel.add_log(
                f"{emoji} {result['contact_name']} - {result.get('detail', result['status'])}",
                "success" if result["status"] == "success" else "error"
            )
        self.after(0, _update)

    def _on_log(self, message, level):
        self.after(0, lambda: self.log_panel.add_log(message, level))

    def _on_state_change(self, state):
        def _update():
            if state in ("completed", "error", "idle"):
                self.start_btn.configure(state="normal")
                self.pause_btn.configure(
                    text="⏸  일시정지",
                    fg_color="#b08800", hover_color="#d29922"
                )
                if state == "completed":
                    self.add_log("발송 완료!", "success")
                elif state == "error":
                    self.add_log("발송 오류로 중단. 다시 시작할 수 있습니다.", "error")
                # 발송 완료/중단 후 연락처 리스트 갱신 (발송횟수/시간 업데이트)
                self._refresh_contact_list()
        self.after(0, _update)

    # ── 카톡 친구탭 OCR 기반 오늘 생일자 즉시 발송 ──

    def _send_kakao_birthday(self):
        """카톡 친구탭 자동 → 오늘 생일자에게 자동 메시지."""
        if not self.orchestrator:
            messagebox.showwarning("미지원", "이 기능은 로컬 모드에서만 지원됩니다.")
            return

        # 문구 선택 — 저장된 템플릿 드롭다운 + 직접 입력 병행
        dlg = BirthdaySendDialog(self, self.orchestrator)
        self.wait_window(dlg)
        template_content = (dlg.result or "").strip()
        if not template_content:
            return  # 취소

        if "%이름%" not in template_content:
            cont = messagebox.askyesno(
                "이름 변수 없음",
                "메시지에 '%이름%' 변수가 없습니다.\n"
                "모든 생일자에게 동일한 본문이 발송됩니다.\n\n"
                "그래도 진행할까요?"
            )
            if not cont:
                return

        # 사전 안내
        proceed = messagebox.askokcancel(
            "🎂 생일자 자동 발송",
            "카톡 친구탭의 '오늘 생일자' 에게만 자동으로 메시지를 보냅니다.\n\n"
            "필수 조건:\n"
            "  • 카카오톡 PC 가 친구탭 활성 상태\n"
            "  • 발송 동안 PC 사용 자제\n\n"
            "먼저 미리보기 (드라이런) 합니다."
        )
        if not proceed:
            return

        # 1단계: 드라이런
        try:
            dry = self.orchestrator.run_kakao_birthday_send(
                template_content=template_content, dry_run=True,
            )
        except Exception as e:
            messagebox.showerror("오류", f"드라이런 실패:\n{e}")
            return

        if not dry.get("ok"):
            messagebox.showerror("실패", dry.get("reason", "알 수 없는 오류"))
            return

        sent = dry.get("sent", 0)
        skipped = dry.get("skipped", 0)
        targets = dry.get("targets", [])

        # 발송 대상 미리보기
        today_targets = [t for t in targets if t.get("action") == "dry_run_sent"]
        if not today_targets:
            messagebox.showinfo(
                "오늘 생일자 없음",
                f"오늘 생일자가 식별되지 않았습니다.\n"
                f"(스킵 {skipped}명 — 어제/내일 생일자)"
            )
            return

        preview_lines = []
        for t in today_targets:
            preview_lines.append(f"  • {t.get('name', '?')}")
            preview = t.get("preview", "")
            if preview:
                preview_lines.append(f"    └ {preview[:60]}...")

        confirm = messagebox.askyesno(
            "발송 확인",
            f"오늘 생일자 {sent}명에게 발송합니다.\n"
            f"(어제/내일 생일자 {skipped}명 자동 스킵)\n\n"
            + "\n".join(preview_lines[:20])
            + "\n\n실제로 발송할까요?"
        )
        if not confirm:
            return

        # 2단계: 실제 발송
        try:
            real = self.orchestrator.run_kakao_birthday_send(
                template_content=template_content, dry_run=False,
            )
        except Exception as e:
            messagebox.showerror("오류", f"발송 실패:\n{e}")
            return

        if real.get("ok"):
            messagebox.showinfo(
                "발송 완료",
                f"발송: {real['sent']}명\n"
                f"스킵: {real['skipped']}명\n"
                f"오류: {len(real.get('errors', []))}건"
            )
        else:
            messagebox.showerror("실패", real.get("reason", ""))

    def _open_birthday_schedule_dialog(self):
        """매일 생일자 자동발송 설정 다이얼로그.

        scheduler.auto_send_settings 의 enabled/시간/모드/템플릿 편집.
        모드 = kakao_ocr (카톡 친구탭 OCR 기반 오늘 생일자 자동 식별 + 발송)
        """
        if not self.orchestrator:
            return
        dialog = BirthdayScheduleDialog(self, self.orchestrator)
        self.wait_window(dialog)


class BirthdayScheduleDialog(ctk.CTkToplevel):
    """매일 생일자 자동발송 설정 다이얼로그.

    scheduler.auto_send_settings 의 다음 필드를 편집:
      - enabled (자동발송 켜기/끄기)
      - mode = "kakao_ocr" (강제, 카톡 친구탭 OCR)
      - send_hour, send_minute
      - birthday_template_id (사용할 템플릿)
    """

    def __init__(self, parent, orchestrator):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.title("📅 매일 생일자 자동 발송 설정")
        self.geometry("480x420")
        self.configure(fg_color=T.BG_DARK)
        self.transient(parent)
        self.grab_set()
        self._build()
        self._load_current()

    def _build(self):
        ctk.CTkLabel(
            self, text="🎂 매일 생일자 자동 발송",
            font=(T.get_font_family(), 16, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            self,
            text="설정한 시각에 매일 자동으로 카톡 친구탭에서\n"
                 "오늘 생일자를 찾아 메시지를 발송합니다.",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_SECONDARY,
            justify="center",
        ).pack(pady=(0, 14))

        # 활성화 토글
        toggle_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=8)
        toggle_frame.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(
            toggle_frame, text="자동 발송:",
            font=(T.get_font_family(), 12, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=14, pady=12)
        self.enabled_var = ctk.BooleanVar(value=False)
        self.enabled_switch = ctk.CTkSwitch(
            toggle_frame, text="",
            variable=self.enabled_var,
            progress_color=T.ACCENT,
        )
        self.enabled_switch.pack(side="left", padx=8)

        # 발송 시간
        time_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=8)
        time_frame.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(
            time_frame, text="발송 시간:",
            font=(T.get_font_family(), 12, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=14, pady=12)

        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        self.hour_var = ctk.StringVar(value="09")
        ctk.CTkOptionMenu(
            time_frame, values=hours, variable=self.hour_var,
            width=70, height=30,
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=4, pady=10)
        ctk.CTkLabel(
            time_frame, text="시", text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=2)

        self.min_var = ctk.StringVar(value="00")
        ctk.CTkOptionMenu(
            time_frame, values=minutes, variable=self.min_var,
            width=70, height=30,
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=4, pady=10)
        ctk.CTkLabel(
            time_frame, text="분", text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=2)

        # 템플릿 선택
        tmpl_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=8)
        tmpl_frame.pack(fill="x", padx=24, pady=(0, 14))
        ctk.CTkLabel(
            tmpl_frame, text="메시지 템플릿:",
            font=(T.get_font_family(), 12, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=14, pady=12)

        # 템플릿 목록
        self._template_id_map = {}
        tmpl_names = ["(선택 안함)"]
        if self.orchestrator:
            try:
                templates = self.orchestrator.message_engine.get_templates()
                for t in templates:
                    tmpl_names.append(t.name)
                    self._template_id_map[t.name] = t.id
            except Exception:
                pass

        self.tmpl_var = ctk.StringVar(value="(선택 안함)")
        ctk.CTkOptionMenu(
            tmpl_frame, values=tmpl_names, variable=self.tmpl_var,
            width=240, height=30,
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=4, pady=10)

        # 안내
        ctk.CTkLabel(
            self,
            text="⚠️ 자동 발송은 카톡 친구탭 OCR 모드로 실행됩니다.\n"
                 "발송 시각에 PC 가 켜져 있고 카톡 PC 가 실행 중이어야 합니다.",
            font=(T.get_font_family(), 10),
            text_color="#f0b90b",
            justify="left", wraplength=420,
        ).pack(padx=24, pady=(0, 10))

        # 버튼
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=10)
        ctk.CTkButton(
            btn_frame, text="취소", width=100, height=36,
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self.destroy
        ).pack(side="left")
        ctk.CTkButton(
            btn_frame, text="저장", width=120, height=36,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, corner_radius=6,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            command=self._save
        ).pack(side="right")

    def _load_current(self):
        """현재 auto_send_settings 값을 UI 에 로드"""
        if not self.orchestrator:
            return
        s = self.orchestrator.scheduler.auto_send_settings
        # 카톡 OCR 모드일 때만 enabled 켜짐 (이 다이얼로그는 OCR 모드 전용)
        is_ocr_mode = s.get("mode", "json") == "kakao_ocr"
        self.enabled_var.set(s.get("enabled", False) and is_ocr_mode)
        self.hour_var.set(f"{int(s.get('send_hour', 9)):02d}")
        self.min_var.set(f"{int(s.get('send_minute', 0)):02d}")

        # 템플릿
        bd_id = s.get("birthday_template_id", "")
        if bd_id and self.orchestrator:
            t = self.orchestrator.message_engine.get_template_by_id(bd_id)
            if t:
                self.tmpl_var.set(t.name)

    def _save(self):
        if not self.orchestrator:
            return
        try:
            tmpl_name = self.tmpl_var.get()
            tmpl_id = self._template_id_map.get(tmpl_name, "")

            if self.enabled_var.get() and not tmpl_id:
                messagebox.showwarning(
                    "템플릿 필요",
                    "자동 발송을 활성화하려면 메시지 템플릿을 선택해주세요."
                )
                return

            self.orchestrator.scheduler.auto_send_settings.update({
                "enabled": self.enabled_var.get(),
                "mode": "kakao_ocr",  # 매일 생일자 자동 = OCR 모드
                "birthday_template_id": tmpl_id,
                "send_hour": int(self.hour_var.get()),
                "send_minute": int(self.min_var.get()),
            })
            self.orchestrator.scheduler.save()

            state = "활성화" if self.enabled_var.get() else "비활성화"
            messagebox.showinfo(
                "저장 완료",
                f"매일 생일자 자동 발송: {state}\n"
                f"시간: {self.hour_var.get()}:{self.min_var.get()}\n"
                f"템플릿: {tmpl_name}"
            )
            self.destroy()
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패:\n{e}")


class BirthdaySendDialog(ctk.CTkToplevel):
    """생일자 즉시발송 — 저장된 템플릿 선택(드롭다운) + 직접 입력 병행.

    확정 시 self.result 에 본문 문자열, 취소 시 None.
    """

    def __init__(self, parent, orchestrator):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.result = None
        self._template_map = {}  # name → template 객체
        self.title("🎂 생일자 즉시발송 - 문구 선택")
        self.geometry("520x460")
        self.configure(fg_color=T.BG_DARK)
        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="🎂 생일자 즉시발송",
            font=(T.get_font_family(), 16, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(pady=(18, 2))
        ctk.CTkLabel(
            self,
            text="저장된 템플릿을 선택하거나 직접 입력하세요. (%이름% 변수 사용 가능)",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_SECONDARY,
        ).pack(pady=(0, 12))

        # 템플릿 드롭다운
        row = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=8)
        row.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(
            row, text="템플릿:", font=(T.get_font_family(), 12, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=14, pady=12)

        names = ["(직접 입력)"]
        if self.orchestrator:
            try:
                for t in self.orchestrator.message_engine.get_templates():
                    names.append(t.name)
                    self._template_map[t.name] = t
            except Exception:
                pass
        self.tmpl_var = ctk.StringVar(value="(직접 입력)")
        ctk.CTkOptionMenu(
            row, values=names, variable=self.tmpl_var,
            width=300, height=30, command=self._on_pick,
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=4, pady=10)

        # 본문 편집
        ctk.CTkLabel(
            self, text="발송 문구:", font=(T.get_font_family(), 12, "bold"),
            text_color=T.TEXT_PRIMARY, anchor="w",
        ).pack(fill="x", padx=24)
        self.editor = ctk.CTkTextbox(
            self, height=150, fg_color=T.BG_INPUT,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
        )
        self.editor.pack(fill="both", expand=True, padx=24, pady=(4, 10))
        self.editor.insert("1.0", "🎂 %이름%님, 생일 진심으로 축하드립니다!")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkButton(
            btns, text="취소", width=90, height=36,
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self._cancel,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            btns, text="미리보기 후 발송 →", width=170, height=36,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, corner_radius=6,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            command=self._confirm,
        ).pack(side="right")

    def _on_pick(self, name):
        t = self._template_map.get(name)
        if t is None:
            return  # (직접 입력)
        contents = getattr(t, "contents", None)
        content = (contents[0] if contents else getattr(t, "content", "")) or ""
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)

    def _confirm(self):
        text = self.editor.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning(
                "문구 필요", "발송할 문구를 입력하거나 템플릿을 선택하세요.",
                parent=self,
            )
            return
        self.result = text
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class ScheduleDialog(ctk.CTkToplevel):
    """예약 발송 시간 설정 다이얼로그"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("예약 발송")
        self.geometry("400x360")
        self.configure(fg_color=T.BG_DARK)
        self.result = None
        self.recurring = "none"  # "none" | "daily"
        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self):
        from datetime import datetime, timedelta

        ctk.CTkLabel(
            self, text="⏰ 예약 발송 시간 설정",
            font=(T.get_font_family(), T.FONT_SIZE_HEADER, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(padx=24, pady=(24, 16))

        # 날짜
        date_frame = ctk.CTkFrame(self, fg_color="transparent")
        date_frame.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkLabel(
            date_frame, text="날짜:",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 8))

        now = datetime.now()
        years = [str(y) for y in range(now.year, now.year + 2)]
        months = [f"{m:02d}" for m in range(1, 13)]
        days = [f"{d:02d}" for d in range(1, 32)]

        self.year_var = ctk.StringVar(value=str(now.year))
        ctk.CTkOptionMenu(
            date_frame, values=years, variable=self.year_var,
            width=80, height=30, font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY
        ).pack(side="left", padx=2)

        ctk.CTkLabel(date_frame, text="-", text_color=T.TEXT_MUTED).pack(side="left")

        self.month_var = ctk.StringVar(value=f"{now.month:02d}")
        ctk.CTkOptionMenu(
            date_frame, values=months, variable=self.month_var,
            width=60, height=30, font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY
        ).pack(side="left", padx=2)

        ctk.CTkLabel(date_frame, text="-", text_color=T.TEXT_MUTED).pack(side="left")

        self.day_var = ctk.StringVar(value=f"{now.day:02d}")
        ctk.CTkOptionMenu(
            date_frame, values=days, variable=self.day_var,
            width=60, height=30, font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY
        ).pack(side="left", padx=2)

        # 시간
        time_frame = ctk.CTkFrame(self, fg_color="transparent")
        time_frame.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkLabel(
            time_frame, text="시간:",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 8))

        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]

        self.hour_var = ctk.StringVar(value=f"{now.hour:02d}")
        ctk.CTkOptionMenu(
            time_frame, values=hours, variable=self.hour_var,
            width=60, height=30, font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY
        ).pack(side="left", padx=2)

        ctk.CTkLabel(time_frame, text=":", text_color=T.TEXT_MUTED).pack(side="left")

        self.min_var = ctk.StringVar(value=f"{(now.minute // 5 * 5):02d}")
        ctk.CTkOptionMenu(
            time_frame, values=minutes, variable=self.min_var,
            width=60, height=30, font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY
        ).pack(side="left", padx=2)

        # 반복 옵션
        repeat_frame = ctk.CTkFrame(self, fg_color="transparent")
        repeat_frame.pack(fill="x", padx=24, pady=(8, 0))
        ctk.CTkLabel(
            repeat_frame, text="반복:",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 8))
        self.recurring_var = ctk.StringVar(value="1회만")
        ctk.CTkOptionMenu(
            repeat_frame, values=["1회만", "매일 같은 시간"],
            variable=self.recurring_var,
            width=180, height=30, font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        # 버튼
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=16)

        ctk.CTkButton(
            btn_frame, text="취소", width=100, height=36,
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="⏰ 예약 등록", width=140, height=36,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, corner_radius=6,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            command=self._confirm
        ).pack(side="right")

    def _confirm(self):
        from datetime import datetime
        try:
            dt = datetime(
                int(self.year_var.get()),
                int(self.month_var.get()),
                int(self.day_var.get()),
                int(self.hour_var.get()),
                int(self.min_var.get())
            )
            if dt <= datetime.now():
                messagebox.showwarning("시간 오류", "현재 시간 이후로 설정해주세요.")
                return
            self.result = dt.isoformat()
            # 반복 옵션
            if self.recurring_var.get() == "매일 같은 시간":
                self.recurring = "daily"
            else:
                self.recurring = "none"
            self.destroy()
        except ValueError as e:
            messagebox.showwarning("날짜 오류", f"올바른 날짜를 입력해주세요.\n{e}")
