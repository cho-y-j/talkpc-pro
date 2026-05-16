"""
Dashboard Page - 메인 대시보드
카카오톡 자동 발송 앱의 메인 랜딩 페이지
"""

import customtkinter as ctk
from tkinter import ttk
from datetime import datetime
from ui.theme import AppTheme as T
from ui.components.widgets import StatCard, LogPanel


class DashboardPage(ctk.CTkFrame):
    """대시보드 페이지 - 통계, 빠른 실행, 로그, 발송 현황"""

    def __init__(self, parent, orchestrator=None, api_client=None, **kwargs):
        super().__init__(parent, fg_color=T.BG_DARK, **kwargs)
        self.orchestrator = orchestrator
        self.api_client = api_client
        self._build()
        self.refresh_stats()

    # ------------------------------------------------------------------ #
    #  UI Build
    # ------------------------------------------------------------------ #
    def _build(self):
        # ── 1. Top Stats Row ──────────────────────────────────────────
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=(20, 12))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stat")

        self.stat_total = StatCard(stats_frame, "총 연락처", "0명", T.INFO)
        self.stat_total.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.stat_sent = StatCard(stats_frame, "오늘 발송", "0건", T.ACCENT)
        self.stat_sent.grid(row=0, column=1, padx=6, sticky="ew")

        self.stat_remaining = StatCard(stats_frame, "오늘 미발송", "0건", T.WARNING)
        self.stat_remaining.grid(row=0, column=2, padx=6, sticky="ew")

        self.stat_rate = StatCard(stats_frame, "성공률", "0%", T.SUCCESS)
        self.stat_rate.grid(row=0, column=3, padx=(6, 0), sticky="ew")

        # ── 2. Quick Action Buttons ───────────────────────────────────
        action_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.CARD_RADIUS,
                                    border_width=1, border_color=T.BORDER)
        action_frame.pack(fill="x", padx=24, pady=(0, 12))

        btn_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=T.CARD_PADDING, pady=T.CARD_PADDING)

        ctk.CTkButton(
            btn_row, text="카카오톡 초기화",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY,
            height=T.BUTTON_HEIGHT, corner_radius=6,
            command=self._on_initialize
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="📐 카카오톡 자동 배치",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color="#2ea043", hover_color="#3fb950",
            text_color=T.TEXT_PRIMARY,
            height=T.BUTTON_HEIGHT, corner_radius=6,
            command=self._on_arrange_kakao
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="📊 발송이력 엑셀 저장",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY,
            height=T.BUTTON_HEIGHT, corner_radius=6,
            command=self._on_export_history
        ).pack(side="left")

        # ── 3. Main Content (Log left 60% | Send history right 40%) ──
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        content.grid_columnconfigure(0, weight=6)
        content.grid_columnconfigure(1, weight=4)
        content.grid_rowconfigure(0, weight=1)

        # -- Left: 발송 로그 --
        self._build_log_panel(content)

        # -- Right: 오늘 발송 현황 --
        self._build_history_panel(content)

    # ---- Log Panel (left) ----
    def _build_log_panel(self, parent):
        log_card = ctk.CTkFrame(parent, fg_color=T.BG_CARD, corner_radius=T.CARD_RADIUS,
                                border_width=1, border_color=T.BORDER)
        log_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        # header
        header = ctk.CTkFrame(log_card, fg_color="transparent", height=40)
        header.pack(fill="x", padx=T.CARD_PADDING, pady=(T.CARD_PADDING, 6))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="발송 로그",
            font=(T.get_font_family(), T.FONT_SIZE_HEADER, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        ctk.CTkButton(
            header, text="지우기", width=60, height=26,
            font=(T.get_font_family(), T.FONT_SIZE_TINY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_SECONDARY, corner_radius=4,
            command=self._clear_log
        ).pack(side="right")

        # textbox - large, font 12
        self.log_textbox = ctk.CTkTextbox(
            log_card,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT,
            text_color=T.TEXT_SECONDARY,
            corner_radius=6,
            border_width=0,
            state="disabled",
            wrap="word"
        )
        self.log_textbox.pack(fill="both", expand=True,
                              padx=T.CARD_PADDING, pady=(0, T.CARD_PADDING))

        # configure color tags
        self.log_textbox.tag_config("success", foreground=T.SUCCESS)
        self.log_textbox.tag_config("error", foreground=T.ERROR)
        self.log_textbox.tag_config("warning", foreground=T.WARNING)
        self.log_textbox.tag_config("info", foreground=T.TEXT_SECONDARY)

    # ---- History Panel (right) ----
    def _build_history_panel(self, parent):
        hist_card = ctk.CTkFrame(parent, fg_color=T.BG_CARD, corner_radius=T.CARD_RADIUS,
                                 border_width=1, border_color=T.BORDER)
        hist_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        # header — 제목 + 날짜 선택
        hist_header = ctk.CTkFrame(hist_card, fg_color="transparent")
        hist_header.pack(fill="x", padx=T.CARD_PADDING, pady=(T.CARD_PADDING, 8))
        ctk.CTkLabel(
            hist_header, text="📅 발송 현황",
            font=(T.get_font_family(), T.FONT_SIZE_HEADER, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        # 날짜 선택 (최근 30일)
        from datetime import datetime as _dt, timedelta as _td
        today = _dt.now().date()
        date_options = []
        for i in range(30):
            d = today - _td(days=i)
            label = "오늘" if i == 0 else ("어제" if i == 1 else d.strftime("%m-%d"))
            date_options.append(f"{label} ({d.isoformat()})")

        self._history_date_var = ctk.StringVar(value=date_options[0])
        self._history_date_menu = ctk.CTkOptionMenu(
            hist_header, values=date_options,
            variable=self._history_date_var,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, height=28, corner_radius=4, width=160,
            command=lambda v: self._refresh_history(),
        )
        self._history_date_menu.pack(side="right")

        # dark treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dashboard.Treeview",
                        background=T.BG_INPUT,
                        foreground=T.TEXT_PRIMARY,
                        fieldbackground=T.BG_INPUT,
                        borderwidth=0,
                        font=(T.get_font_family(), T.FONT_SIZE_BODY),
                        rowheight=28)
        style.configure("Dashboard.Treeview.Heading",
                        background=T.BG_HOVER,
                        foreground=T.TEXT_PRIMARY,
                        borderwidth=0,
                        font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"))
        style.map("Dashboard.Treeview",
                  background=[("selected", T.BG_HOVER)],
                  foreground=[("selected", T.TEXT_PRIMARY)])
        style.map("Dashboard.Treeview.Heading",
                  background=[("active", T.BG_HOVER)])

        # treeview
        tree_frame = ctk.CTkFrame(hist_card, fg_color=T.BG_INPUT, corner_radius=6)
        tree_frame.pack(fill="both", expand=True,
                        padx=T.CARD_PADDING, pady=(0, 8))

        self.history_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "status", "time"),
            show="headings",
            style="Dashboard.Treeview",
            selectmode="browse"
        )
        self.history_tree.heading("name", text="이름")
        self.history_tree.heading("status", text="상태")
        self.history_tree.heading("time", text="시간")
        self.history_tree.column("name", width=90, minwidth=60)
        self.history_tree.column("status", width=60, minwidth=50, anchor="center")
        self.history_tree.column("time", width=70, minwidth=50, anchor="center")

        # color tags for treeview rows
        self.history_tree.tag_configure("success", foreground=T.SUCCESS)
        self.history_tree.tag_configure("failed", foreground=T.ERROR)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical",
                                  command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scrollbar.pack(side="right", fill="y", pady=4)

        # bottom buttons
        btn_row = ctk.CTkFrame(hist_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=T.CARD_PADDING, pady=(0, T.CARD_PADDING))

        ctk.CTkButton(
            btn_row, text="실패 재발송",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.ERROR, hover_color="#da3633",
            text_color=T.TEXT_PRIMARY,
            height=T.BUTTON_HEIGHT, corner_radius=6,
            command=self._on_retry_failed
        ).pack(side="left", padx=(0, 8), fill="x", expand=True)

        ctk.CTkButton(
            btn_row, text="이어서 보내기",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT,
            height=T.BUTTON_HEIGHT, corner_radius=6,
            command=self._on_resume_send
        ).pack(side="left", fill="x", expand=True)

    # ------------------------------------------------------------------ #
    #  Public API (called by app.py)
    # ------------------------------------------------------------------ #
    def refresh_stats(self):
        """통계 카드 + 발송 현황 테이블 갱신"""
        if not self.orchestrator:
            return

        # stat cards
        try:
            stats = self.orchestrator.contact_mgr.get_send_stats()
            self.stat_total.update_value(f"{stats.get('total_contacts', 0)}명")
            self.stat_sent.update_value(f"{stats.get('sent_today', 0)}건")
            self.stat_remaining.update_value(f"{stats.get('remaining_today', 0)}건")
        except Exception:
            pass

        try:
            report = self.orchestrator.report.get_statistics()
            rate = report.get("success_rate", 0)
            rate_str = f"{rate:.0f}%" if isinstance(rate, (int, float)) else f"{rate}"
            color = T.SUCCESS if (isinstance(rate, (int, float)) and rate >= 80) else T.ERROR
            self.stat_rate.update_value(rate_str, color)
        except Exception:
            pass

        # refresh history treeview
        self._refresh_history()

    def auto_initialize(self):
        """
        앱 시작 시 자동 초기화
        1. 카카오톡 찾기
        2. 카카오톡 창을 고정 위치로 이동
        3. 학습 좌표 있으면 로드, 없으면 디폴트 좌표 자동 계산
        4. 발송 준비 완료
        """
        if not self.orchestrator:
            return

        import json

        # 1. 카카오톡 찾기
        if not self.orchestrator.window_ctrl.find_kakao_window():
            self.add_log("카카오톡이 실행되어 있지 않습니다.", "warning")
            return

        self.add_log("카카오톡 발견!", "success")

        # 2. 카카오톡 창을 고정 위치로 이동 (포그라운드 전환 없이)
        self.orchestrator.window_ctrl.calculate_kakao_position()
        try:
            import win32gui
            rect = self.orchestrator.window_ctrl.kakao_rect
            if rect:
                def find_cb(hwnd, results):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if self.orchestrator.window_ctrl._is_kakao_window(title):
                            results.append(hwnd)
                    return True
                hwnds = []
                win32gui.EnumWindows(find_cb, hwnds)
                if hwnds:
                    win32gui.MoveWindow(
                        hwnds[0],
                        rect["x"], rect["y"],
                        rect["width"], rect["height"],
                        True
                    )
                    self.add_log(
                        f"카카오톡 배치: ({rect['x']},{rect['y']}) "
                        f"{rect['width']}x{rect['height']}", "info"
                    )
        except Exception as e:
            self.add_log(f"카카오톡 배치 실패: {e}", "warning")

        # 3. 좌표: 학습 파일 있으면 사용, 없으면 디폴트 자동 계산
        positions_path = self.orchestrator.base_dir / "config" / "learned_positions.json"
        if positions_path.exists():
            with open(positions_path, "r", encoding="utf-8") as f:
                self.orchestrator.coordinates = json.load(f)
            self.add_log("학습 좌표 로드", "success")
        else:
            coords = self.orchestrator.window_ctrl.calculate_ui_coordinates()
            self.orchestrator.coordinates = coords
            self.add_log("디폴트 좌표 자동 계산 완료", "success")

        # 4. 발송 준비
        result = self.orchestrator.confirm_calibration()
        if result.get("success"):
            self.add_log("발송 준비 완료!", "success")
        else:
            self.add_log("초기화 실패", "error")

    def add_log(self, message: str, level: str = "info"):
        """외부에서 로그 추가 (app.py 등에서 호출)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = level if level in ("success", "error", "warning", "info") else "info"

        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n", tag)
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    # ------------------------------------------------------------------ #
    #  Internal: Initialization
    # ------------------------------------------------------------------ #
    def _do_initialize(self, use_learned: bool):
        """카카오톡 초기화 공통 로직 (창 위치 건드리지 않음)"""
        if not self.orchestrator:
            return

        # 1. 카카오톡 찾기 (활성화만, 위치 이동 안 함)
        if not self.orchestrator.window_ctrl.find_kakao_window():
            self.add_log("카카오톡이 실행되어 있지 않습니다!", "error")
            return

        self.add_log("카카오톡 발견!", "success")

        # 2. 좌표 설정 (학습 좌표 있으면 사용, 없으면 현재 창 위치 기반 자동 계산)
        if not use_learned:
            result = self.orchestrator.auto_detect_coordinates()
            if result.get("success"):
                self.add_log("카카오톡 현재 위치 기반 좌표 자동 설정!", "success")
            else:
                self.add_log(f"자동 좌표 계산 실패: {result.get('error')}", "error")
                return

        # 3. 캘리브레이션 확인
        result = self.orchestrator.confirm_calibration()
        if result.get("success"):
            self.add_log("초기화 완료! 발송 준비 완료.", "success")
        else:
            self.add_log("초기화 실패", "error")

    # ------------------------------------------------------------------ #
    #  Internal: Button handlers
    # ------------------------------------------------------------------ #
    def _on_initialize(self):
        """카카오톡 초기화 버튼"""
        if not self.orchestrator:
            return

        positions_path = self.orchestrator.base_dir / "config" / "learned_positions.json"
        use_learned = False

        if positions_path.exists():
            import json
            with open(positions_path, "r", encoding="utf-8") as f:
                positions = json.load(f)
            self.add_log("저장된 학습 위치 로드 중...", "info")
            self.orchestrator.coordinates = positions
            use_learned = True
        else:
            self.add_log("학습 파일 없음 - 디폴트 좌표 자동 계산 모드", "info")

        self._do_initialize(use_learned)
        self.refresh_stats()

    def _on_arrange_kakao(self):
        """카카오톡 창 자동 배치 (settings 의 _position_kakao 와 동일 동작)"""
        if not self.orchestrator:
            return
        if not self.orchestrator.window_ctrl.find_kakao_window():
            self.add_log("카카오톡이 실행되어 있지 않습니다!", "error")
            from tkinter import messagebox
            messagebox.showwarning(
                "카카오톡 없음",
                "카카오톡 PC를 먼저 실행해주세요."
            )
            return
        self.orchestrator.window_ctrl.activate_kakao()
        self.orchestrator.window_ctrl.calculate_kakao_position()
        ok = self.orchestrator.window_ctrl.position_kakao_window()
        if ok:
            rect = self.orchestrator.window_ctrl.kakao_rect
            self.add_log(
                f"카카오톡 자동 배치 완료: ({rect['x']}, {rect['y']}) "
                f"{rect['width']}x{rect['height']}", "success"
            )
        else:
            self.add_log("카카오톡 자동 배치 실패 — 수동 배치 필요", "warning")

    def _on_export_history(self):
        """발송 이력을 엑셀 파일로 저장 (오늘 발송 + 카톡 자동화 audit 로그)"""
        from tkinter import filedialog, messagebox
        from datetime import datetime as _dt

        filepath = filedialog.asksaveasfilename(
            title="발송 이력 저장",
            defaultextension=".xlsx",
            initialfile=f"발송이력_{_dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not filepath:
            return

        if not self.orchestrator:
            return

        try:
            import openpyxl
            from pathlib import Path
            import json

            wb = openpyxl.Workbook()

            # 시트 1: 연락처별 발송 통계
            ws1 = wb.active
            ws1.title = "연락처 발송 이력"
            ws1.append(["이름", "카테고리", "전화번호", "마지막 발송", "총 발송 횟수"])
            for c in self.orchestrator.contact_mgr.get_all():
                ws1.append([
                    c.name, c.category, c.phone or "",
                    c.last_sent or "", c.send_count,
                ])
            for col_idx in range(1, 6):
                ws1.column_dimensions[chr(64 + col_idx)].width = 18

            # 시트 2: 카톡 자동화 audit 로그 (kakao_runs/)
            ws2 = wb.create_sheet("카톡 자동화 이력")
            ws2.append(["일시", "종류", "결과", "추가/발송", "이름 목록 / 사유"])
            log_dir = Path("logs/kakao_runs")
            if log_dir.exists():
                for log_file in sorted(log_dir.glob("*.json"), reverse=True):
                    try:
                        with open(log_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        ts = data.get("timestamp", "")[:19].replace("T", " ")
                        kind = data.get("kind", "")
                        ok = "성공" if data.get("ok") else "실패"
                        added = data.get("added", data.get("sent", 0))
                        names = data.get("names", []) or []
                        detail = (", ".join(names[:30]) if names
                                  else data.get("reason", ""))
                        ws2.append([ts, kind, ok, added, detail])
                    except Exception:
                        continue
            for col_idx in range(1, 6):
                ws2.column_dimensions[chr(64 + col_idx)].width = 22

            wb.save(filepath)
            self.add_log(f"발송 이력 저장 완료: {filepath}", "success")
            messagebox.showinfo(
                "저장 완료",
                f"발송 이력 엑셀 파일이 저장되었습니다.\n\n{filepath}"
            )
        except Exception as e:
            self.add_log(f"발송 이력 저장 실패: {e}", "error")
            messagebox.showerror("실패", f"엑셀 저장 중 오류:\n{e}")

    def _on_retry_failed(self):
        """실패 건 재발송"""
        if not self.orchestrator:
            return
        count = self.orchestrator.retry_failed()
        if count and count > 0:
            self.add_log(f"실패 {count}건 재발송 큐 로드 완료", "info")
            self.winfo_toplevel()._navigate("send")
        else:
            self.add_log("재발송할 실패 건이 없습니다.", "warning")

    def _on_resume_send(self):
        """저장된 큐 상태에서 이어서 보내기"""
        if not self.orchestrator:
            return
        loaded = self.orchestrator.load_queue_state()
        if loaded:
            self.add_log("저장된 발송 큐 로드 완료 - 발송 페이지로 이동", "info")
            self.winfo_toplevel()._navigate("send")
        else:
            self.add_log("저장된 발송 큐가 없습니다.", "warning")

    # ------------------------------------------------------------------ #
    #  Internal: Helpers
    # ------------------------------------------------------------------ #
    def _clear_log(self):
        """로그 지우기"""
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def _refresh_history(self):
        """선택된 날짜의 발송 현황 테이블 갱신"""
        # clear
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        if not self.orchestrator:
            return

        # 선택된 날짜 파싱
        selected = self._history_date_var.get() if hasattr(self, "_history_date_var") else ""
        target_date = None
        if "(" in selected and ")" in selected:
            try:
                target_date = selected.split("(")[1].rstrip(")")  # "YYYY-MM-DD"
            except Exception:
                pass
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        is_today = (target_date == datetime.now().strftime("%Y-%m-%d"))

        entries = []  # [(name, status_raw, recorded), ...]

        # 1) 오늘이면 current_session 도 포함 (라이브 발송)
        if is_today:
            try:
                for entry in self.orchestrator.report.current_session or []:
                    entries.append((
                        entry.get("contact_name", "-"),
                        entry.get("status", ""),
                        entry.get("recorded_at", ""),
                    ))
            except Exception:
                pass

        # 2) 디스크 session 로그 로드 (해당 날짜)
        import json
        from pathlib import Path as _Path
        log_dir = _Path("logs")
        if log_dir.exists():
            for fp in sorted(log_dir.glob(f"session_{target_date.replace('-', '')}_*.json")):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for r in data.get("results", []):
                        entries.append((
                            r.get("contact_name", "-"),
                            r.get("status", ""),
                            r.get("recorded_at", ""),
                        ))
                except Exception:
                    continue

        # 3) 카톡 자동화 audit 로그 (kakao_runs/) 도 같은 날짜 포함
        kakao_dir = _Path("logs/kakao_runs")
        if kakao_dir.exists():
            for fp in sorted(kakao_dir.glob(f"*_{target_date.replace('-', '')}_*.json")):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    kind = data.get("kind", "")
                    ts = data.get("timestamp", "")
                    for n in (data.get("names") or [])[:50]:
                        entries.append((
                            f"[{kind}] {n}",
                            "success" if data.get("ok") else "failed",
                            ts,
                        ))
                except Exception:
                    continue

        if not entries:
            self.history_tree.insert("", "end",
                                     values=("(이력 없음)", "-", "-"),
                                     tags=("failed",))
            return

        for name, status_raw, recorded in entries:
            status_display = "성공" if status_raw == "success" else "실패"
            tag = "success" if status_raw == "success" else "failed"

            time_str = "-"
            if recorded:
                try:
                    dt = datetime.fromisoformat(str(recorded))
                    time_str = dt.strftime("%H:%M:%S")
                except (ValueError, TypeError):
                    time_str = str(recorded)[-8:] if len(str(recorded)) >= 8 else str(recorded)

            self.history_tree.insert("", "end",
                                     values=(name, status_display, time_str),
                                     tags=(tag,))

        children = self.history_tree.get_children()
        if children:
            self.history_tree.see(children[-1])
