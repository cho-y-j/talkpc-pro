"""
Message Page - 메시지 템플릿 관리 페이지
여러 변형 메시지 지원 (랜덤 발송으로 봇 탐지 방지)
"""

import customtkinter as ctk
from tkinter import messagebox
from ui.theme import AppTheme as T


class MessagePage(ctk.CTkFrame):
    """메시지 템플릿 관리 페이지"""

    def __init__(self, parent, orchestrator=None, **kwargs):
        super().__init__(parent, fg_color=T.BG_DARK, **kwargs)
        self.orchestrator = orchestrator
        self._variation_editors = []   # 변형별 에디터 리스트
        self._current_var_idx = 0      # 현재 보고 있는 변형 인덱스
        self._build()

    def _build(self):
        # -- 헤더 --
        header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        header.pack(fill="x", padx=24, pady=(20, 16))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="💬 메시지 템플릿",
            font=(T.get_font_family(), T.FONT_SIZE_TITLE, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        # -- 좌우 분할 --
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        # -- 좌측: 템플릿 목록 --
        left_panel = ctk.CTkFrame(content, fg_color=T.BG_CARD,
                                   corner_radius=T.CARD_RADIUS,
                                   border_width=1, border_color=T.BORDER)
        left_panel.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        left_header = ctk.CTkFrame(left_panel, fg_color="transparent", height=40)
        left_header.pack(fill="x", padx=12, pady=(12, 8))
        left_header.pack_propagate(False)

        ctk.CTkLabel(
            left_header, text="저장된 템플릿",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        ctk.CTkButton(
            left_header, text="+", width=30, height=26,
            font=(T.get_font_family(), 14, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, corner_radius=4,
            command=self._new_template
        ).pack(side="right")

        self.template_list = ctk.CTkScrollableFrame(
            left_panel, fg_color="transparent",
            scrollbar_button_color=T.BG_HOVER
        )
        self.template_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # -- 우측: 에디터 --
        right_panel = ctk.CTkFrame(content, fg_color=T.BG_CARD,
                                    corner_radius=T.CARD_RADIUS,
                                    border_width=1, border_color=T.BORDER)
        right_panel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self._right_panel = right_panel

        # 에디터 헤더
        editor_header = ctk.CTkFrame(right_panel, fg_color="transparent", height=40)
        editor_header.pack(fill="x", padx=16, pady=(16, 8))
        editor_header.pack_propagate(False)

        ctk.CTkLabel(
            editor_header, text="메시지 편집기",
            font=(T.get_font_family(), T.FONT_SIZE_HEADER, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        ctk.CTkButton(
            editor_header, text="💾 저장", width=80, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, corner_radius=6,
            command=self._save_template
        ).pack(side="right")

        ctk.CTkButton(
            editor_header, text="🗑", width=30, height=28,
            font=(T.get_font_family(), 12),
            fg_color=T.BG_HOVER, hover_color=T.ERROR,
            text_color=T.TEXT_MUTED, corner_radius=6,
            command=self._delete_template
        ).pack(side="right", padx=(0, 4))

        # 템플릿 이름
        self.name_entry = ctk.CTkEntry(
            right_panel, placeholder_text="템플릿 이름 (예: 새해 인사)",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6
        )
        self.name_entry.pack(fill="x", padx=16, pady=(0, 8))

        # ── 변형 탭 바 ──
        var_bar = ctk.CTkFrame(right_panel, fg_color="transparent", height=32)
        var_bar.pack(fill="x", padx=16, pady=(0, 4))
        var_bar.pack_propagate(False)

        ctk.CTkLabel(
            var_bar, text="메시지 변형:",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 6))

        self._var_tab_frame = ctk.CTkFrame(var_bar, fg_color="transparent")
        self._var_tab_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            var_bar, text="+ 변형 추가", width=80, height=24,
            font=(T.get_font_family(), 9, "bold"),
            fg_color="#1a5276", hover_color="#2471a3",
            text_color="#ffffff", corner_radius=4,
            command=self._add_variation
        ).pack(side="right", padx=(4, 0))

        # 변형 설명
        self._var_info = ctk.CTkLabel(
            right_panel,
            text="변형이 2개 이상이면 발송 시 랜덤으로 선택됩니다 (봇 탐지 방지)",
            font=(T.get_font_family(), 9),
            text_color=T.TEXT_MUTED
        )
        self._var_info.pack(padx=16, anchor="w")

        # 변수 버튼들
        var_frame = ctk.CTkFrame(right_panel, fg_color="transparent", height=32)
        var_frame.pack(fill="x", padx=16, pady=(4, 4))
        var_frame.pack_propagate(False)

        ctk.CTkLabel(
            var_frame, text="변수 삽입:",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        ).pack(side="left", padx=(0, 8))

        variables = ["%이름%", "%카테고리%", "%회사%", "%직급%", "%전화번호%", "%메모%", "%생일%", "%기념일%", "%날짜%", "%요일%"]
        for var in variables:
            ctk.CTkButton(
                var_frame, text=var, width=60, height=24,
                font=(T.get_font_family(), 9),
                fg_color=T.BG_HOVER, hover_color=T.BORDER,
                text_color=T.INFO, corner_radius=4,
                command=lambda v=var: self._insert_variable(v)
            ).pack(side="left", padx=2)

        # 메시지 에디터 (현재 변형)
        self.editor = ctk.CTkTextbox(
            right_panel,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT,
            text_color=T.TEXT_PRIMARY,
            corner_radius=6,
            border_width=1,
            border_color=T.BORDER
        )
        self.editor.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.editor.insert("1.0", "안녕하세요 %이름%님!\n\n여기에 메시지를 작성하세요.\n\n변수를 사용하면 자동으로 치환됩니다.")

        # 이미지 첨부
        img_frame = ctk.CTkFrame(right_panel, fg_color="transparent", height=32)
        img_frame.pack(fill="x", padx=16, pady=(0, 8))
        img_frame.pack_propagate(False)

        self.template_image_path = None

        ctk.CTkButton(
            img_frame, text="📎 이미지 첨부", width=110, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self._select_image
        ).pack(side="left", padx=(0, 6))

        self.img_label = ctk.CTkLabel(
            img_frame, text="첨부 없음",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        )
        self.img_label.pack(side="left", padx=(0, 4))

        self.img_clear_btn = ctk.CTkButton(
            img_frame, text="✕", width=24, height=24,
            font=(T.get_font_family(), 10),
            fg_color="transparent", hover_color=T.ERROR,
            text_color=T.TEXT_MUTED, corner_radius=4,
            command=self._clear_image
        )

        # 이미지 미리보기 영역
        self.img_preview_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        self.img_preview_label = None

        # 미리보기
        preview_label = ctk.CTkLabel(
            right_panel, text="👁 미리보기 (첫 번째 연락처 기준)",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            text_color=T.TEXT_SECONDARY
        )
        preview_label.pack(padx=16, anchor="w")

        self.preview_box = ctk.CTkTextbox(
            right_panel, height=80,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT,
            text_color=T.SUCCESS,
            corner_radius=6,
            state="disabled"
        )
        self.preview_box.pack(fill="x", padx=16, pady=(4, 8))

        # 미리보기 버튼
        ctk.CTkButton(
            right_panel, text="🔄 미리보기 업데이트",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=6,
            command=self._update_preview
        ).pack(padx=16, pady=(0, 16))

        # 현재 편집 중인 템플릿 ID
        self.current_template_id = None

        # 변형 데이터 초기화 (기본 1개)
        self._variation_texts = ["안녕하세요 %이름%님!\n\n여기에 메시지를 작성하세요.\n\n변수를 사용하면 자동으로 치환됩니다."]
        self._current_var_idx = 0
        self._refresh_var_tabs()

        self._refresh_template_list()

    # ── 변형 관리 ──

    def _refresh_var_tabs(self):
        """변형 탭 버튼 갱신"""
        for w in self._var_tab_frame.winfo_children():
            w.destroy()

        for i, _ in enumerate(self._variation_texts):
            is_active = i == self._current_var_idx
            tab_frame = ctk.CTkFrame(self._var_tab_frame, fg_color="transparent")
            tab_frame.pack(side="left", padx=(0, 2))

            ctk.CTkButton(
                tab_frame, text=f"변형 {i + 1}", height=24,
                width=60,
                font=(T.get_font_family(), 9, "bold" if is_active else "normal"),
                fg_color=T.ACCENT if is_active else T.BG_HOVER,
                hover_color=T.ACCENT_HOVER if is_active else T.BORDER,
                text_color=T.TEXT_ON_ACCENT if is_active else T.TEXT_SECONDARY,
                corner_radius=4,
                command=lambda idx=i: self._switch_variation(idx)
            ).pack(side="left")

            # 2개 이상일 때 삭제 버튼
            if len(self._variation_texts) > 1:
                ctk.CTkButton(
                    tab_frame, text="✕", width=18, height=18,
                    font=(T.get_font_family(), 8),
                    fg_color="transparent", hover_color=T.ERROR,
                    text_color=T.TEXT_MUTED, corner_radius=2,
                    command=lambda idx=i: self._remove_variation(idx)
                ).pack(side="left", padx=(1, 0))

        # 변형 개수 안내
        n = len(self._variation_texts)
        if n > 1:
            self._var_info.configure(
                text=f"{n}개 변형 등록됨 → 발송 시 랜덤 선택 (봇 탐지 방지)",
                text_color=T.SUCCESS
            )
        else:
            self._var_info.configure(
                text="변형이 2개 이상이면 발송 시 랜덤으로 선택됩니다 (봇 탐지 방지)",
                text_color=T.TEXT_MUTED
            )

    def _save_current_editor_to_variation(self):
        """현재 에디터 내용을 현재 변형에 저장"""
        text = self.editor.get("1.0", "end").strip()
        if self._current_var_idx < len(self._variation_texts):
            self._variation_texts[self._current_var_idx] = text

    def _switch_variation(self, idx):
        """변형 탭 전환"""
        # 현재 에디터 내용 저장
        self._save_current_editor_to_variation()
        # 새 탭으로 전환
        self._current_var_idx = idx
        self.editor.delete("1.0", "end")
        if idx < len(self._variation_texts):
            self.editor.insert("1.0", self._variation_texts[idx])
        self._refresh_var_tabs()

    def _add_variation(self):
        """변형 추가"""
        # 현재 에디터 저장
        self._save_current_editor_to_variation()
        # 현재 내용을 복사해서 새 변형 추가 (수정 편의)
        current_text = self.editor.get("1.0", "end").strip()
        self._variation_texts.append(current_text)
        # 새 변형으로 이동
        self._current_var_idx = len(self._variation_texts) - 1
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", current_text)
        self._refresh_var_tabs()

    def _remove_variation(self, idx):
        """변형 삭제"""
        if len(self._variation_texts) <= 1:
            return
        if not messagebox.askyesno("변형 삭제", f"변형 {idx + 1}을 삭제하시겠습니까?"):
            return
        self._save_current_editor_to_variation()
        self._variation_texts.pop(idx)
        # 인덱스 조정
        if self._current_var_idx >= len(self._variation_texts):
            self._current_var_idx = len(self._variation_texts) - 1
        # 에디터 갱신
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self._variation_texts[self._current_var_idx])
        self._refresh_var_tabs()

    # ── 템플릿 목록 ──

    def _refresh_template_list(self):
        """템플릿 목록 새로고침"""
        for widget in self.template_list.winfo_children():
            widget.destroy()

        if not self.orchestrator:
            return

        templates = self.orchestrator.message_engine.get_templates()

        for tmpl in templates:
            is_current = tmpl.id == self.current_template_id
            var_count = len(tmpl.contents) if len(tmpl.contents) > 1 else 0
            label = f"📝 {tmpl.name}"
            if var_count:
                label += f" ({var_count}변형)"

            btn = ctk.CTkButton(
                self.template_list,
                text=label,
                font=(T.get_font_family(), T.FONT_SIZE_SMALL),
                fg_color=T.ACCENT if is_current else T.BG_INPUT,
                hover_color=T.BG_HOVER,
                text_color=T.TEXT_ON_ACCENT if is_current else T.TEXT_PRIMARY,
                height=36, corner_radius=6, anchor="w",
                command=lambda t=tmpl: self._load_template(t)
            )
            btn.pack(fill="x", pady=2)

    def _load_template(self, template):
        """템플릿 로드"""
        self.current_template_id = template.id
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, template.name)

        # 변형 데이터 로드
        self._variation_texts = list(template.contents)
        if not self._variation_texts:
            self._variation_texts = [""]
        self._current_var_idx = 0

        # 에디터에 첫 번째 변형 표시
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self._variation_texts[0])
        self._refresh_var_tabs()

        # 이미지 로드
        if template.image_path:
            self._set_image(template.image_path)
        else:
            self._clear_image()
        self._refresh_template_list()
        self._update_preview()

    def _new_template(self):
        """새 템플릿"""
        self.current_template_id = None
        self.name_entry.delete(0, "end")
        self.editor.delete("1.0", "end")
        self._variation_texts = [""]
        self._current_var_idx = 0
        self._clear_image()
        self._refresh_var_tabs()
        self._refresh_template_list()

    def _save_template(self):
        """템플릿 저장"""
        # 현재 에디터 내용 저장
        self._save_current_editor_to_variation()

        name = self.name_entry.get().strip()
        # 빈 변형 제거
        contents = [t for t in self._variation_texts if t.strip()]

        if not name:
            messagebox.showwarning("필수 입력", "템플릿 이름을 입력해주세요.")
            return
        if not contents:
            messagebox.showwarning("필수 입력", "메시지 내용을 입력해주세요.")
            return

        if self.orchestrator:
            img = self.template_image_path or ""
            if self.current_template_id:
                self.orchestrator.message_engine.update_template(
                    self.current_template_id, name=name,
                    contents=contents,
                    content=contents[0],
                    image_path=img
                )
            else:
                tmpl = self.orchestrator.message_engine.add_template(
                    name, contents[0], image_path=img
                )
                tmpl.contents = contents
                self.orchestrator.message_engine.save_templates()
                self.current_template_id = tmpl.id

            self._variation_texts = contents
            if self._current_var_idx >= len(contents):
                self._current_var_idx = 0

            self._refresh_var_tabs()
            self._refresh_template_list()
            var_info = f" ({len(contents)}개 변형)" if len(contents) > 1 else ""
            messagebox.showinfo("저장 완료", f"'{name}' 템플릿이 저장되었습니다.{var_info}")

    def _delete_template(self):
        """템플릿 삭제"""
        if not self.current_template_id:
            return
        if not messagebox.askyesno("삭제 확인", "이 템플릿을 삭제하시겠습니까?"):
            return
        if self.orchestrator:
            self.orchestrator.message_engine.delete_template(self.current_template_id)
        self._new_template()

    def _insert_variable(self, variable: str):
        """에디터에 변수 삽입"""
        self.editor.insert("insert", variable)

    def _select_image(self):
        """이미지 파일 선택"""
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="이미지 선택",
            filetypes=[("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if filepath:
            self._set_image(filepath)

    def _set_image(self, filepath):
        """이미지 경로 설정 + 미리보기"""
        import os
        self.template_image_path = filepath
        filename = os.path.basename(filepath)
        self.img_label.configure(text=filename, text_color=T.ACCENT)
        self.img_clear_btn.pack(side="left")
        self._show_image_preview(filepath)

    def _clear_image(self):
        """이미지 첨부 제거"""
        self.template_image_path = None
        self.img_label.configure(text="첨부 없음", text_color=T.TEXT_MUTED)
        self.img_clear_btn.pack_forget()
        self.img_preview_frame.pack_forget()
        if self.img_preview_label:
            self.img_preview_label.destroy()
            self.img_preview_label = None

    def _show_image_preview(self, filepath):
        """이미지 미리보기 표시"""
        try:
            from PIL import Image, ImageTk
            img = Image.open(filepath)
            img.thumbnail((200, 120), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)

            if self.img_preview_label:
                self.img_preview_label.destroy()

            self.img_preview_frame.pack(fill="x", padx=16, pady=(0, 8))
            import tkinter as tk
            self.img_preview_label = tk.Label(
                self.img_preview_frame, image=self._photo,
                bg="#1c2333", bd=1, relief="solid"
            )
            self.img_preview_label.pack(anchor="w")
        except Exception:
            pass

    def _update_preview(self):
        """미리보기 업데이트"""
        content = self.editor.get("1.0", "end").strip()

        if self.orchestrator:
            contacts = self.orchestrator.contact_mgr.get_all()
            if contacts:
                preview = self.orchestrator.message_engine.substitute(
                    content, contacts[0].to_dict()
                )
            else:
                sample = {
                    "name": "홍길동",
                    "company": "ABC회사",
                    "position": "대리",
                    "phone": "010-1234-5678",
                    "memo": "주요 거래처",
                    "category": "friend",
                    "birthday": "03-15",
                    "anniversary": "05-10"
                }
                preview = self.orchestrator.message_engine.substitute(content, sample)
        else:
            preview = content

        # 이미지 첨부 정보 표시
        if self.template_image_path:
            import os
            preview += f"\n\n📎 첨부 이미지: {os.path.basename(self.template_image_path)}"

        # 변형 개수 표시
        n = len(self._variation_texts)
        if n > 1:
            preview += f"\n\n🎲 {n}개 변형 중 랜덤 선택됨"

        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", preview)
        self.preview_box.configure(state="disabled")

    def get_current_message(self) -> str:
        """현재 에디터의 메시지 반환"""
        return self.editor.get("1.0", "end").strip()
