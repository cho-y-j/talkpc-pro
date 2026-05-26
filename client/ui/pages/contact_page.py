"""
Contact Page - 연락처 관리 페이지
Treeview 기반 고속 테이블 + 커스텀 카테고리
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from ui.theme import AppTheme as T


class ContactPage(ctk.CTkFrame):
    """연락처 관리 페이지"""

    def __init__(self, parent, orchestrator=None, api_client=None, **kwargs):
        super().__init__(parent, fg_color=T.BG_DARK, **kwargs)
        self.orchestrator = orchestrator
        self.api_client = api_client  # SaaS 모드
        self._contacts_cache = []  # API 연락처 캐시
        self._build()

    def _build(self):
        # -- 헤더 --
        header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        header.pack(fill="x", padx=24, pady=(20, 16))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="👥 연락처 관리",
            font=(T.get_font_family(), T.FONT_SIZE_TITLE, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        # 버튼들
        ctk.CTkButton(
            header, text="📥 내보내기", width=90,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=6,
            command=self._export_excel
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header, text="📤 가져오기", width=90,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=6,
            command=self._import_excel
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header, text="🔄 카톡친구", width=100,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color="#27ae60", hover_color="#229954",
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=6,
            command=self._sync_kakao_friends
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header, text="📋 샘플 다운", width=90,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color="#1a5276", hover_color="#2471a3",
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=6,
            command=self._download_sample
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header, text="+ 추가", width=80,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, height=30, corner_radius=6,
            command=self._add_contact
        ).pack(side="right")

        # -- 카테고리 필터 --
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 8))

        self.category_var = ctk.StringVar(value="all")
        self.cat_btn_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        self.cat_btn_frame.pack(side="left", fill="x", expand=True)

        # 카테고리 추가 버튼
        ctk.CTkButton(
            filter_frame, text="+ 카테고리", width=90, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.ACCENT, corner_radius=14,
            command=self._add_category
        ).pack(side="right")

        self._refresh_category_buttons()

        # -- 검색 --
        search_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        search_frame.pack(fill="x", padx=24, pady=(0, 12))
        search_frame.pack_propagate(False)

        self.search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="🔍 이름·회사·메모·생일 검색 (예: 03-15, 3월)...",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search())

        # 생일자 빠른 필터 — 검색창에 값을 넣어 재사용
        ctk.CTkButton(
            search_frame, text="🎂 오늘", width=70, height=36,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.ACCENT,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self._filter_birthday_today,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            search_frame, text="🎂 이번 달", width=80, height=36,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.ACCENT,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self._filter_birthday_month,
        ).pack(side="left", padx=(6, 0))

        # -- Treeview 스타일 (다크 테마) --
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Contact.Treeview",
                         background="#1c2333", foreground="#e6edf3",
                         fieldbackground="#1c2333", borderwidth=0,
                         font=(T.get_font_family(), 11),
                         rowheight=32)
        style.configure("Contact.Treeview.Heading",
                         background="#2d333b", foreground="#e6edf3",
                         font=(T.get_font_family(), 10, "bold"),
                         borderwidth=0)
        style.map("Contact.Treeview",
                   background=[("selected", "#2f81f7")],
                   foreground=[("selected", "#ffffff")])

        # -- Treeview 테이블 --
        tree_frame = ctk.CTkFrame(self, fg_color="#1c2333", corner_radius=8)
        tree_frame.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        # 체크박스 컬럼 추가 — 다중선택용 (영구)
        columns = ("check", "no", "name", "category", "phone", "company", "birthday", "memo")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings",
            selectmode="extended", style="Contact.Treeview"
        )
        # 헤더 — check 헤더 클릭 시 전체선택 토글
        self.tree.heading("check", text="☐", anchor="center",
                          command=self._toggle_all_check)
        self.tree.heading("no", text="#", anchor="center")
        self.tree.heading("name", text="이름", anchor="w")
        self.tree.heading("category", text="카테고리", anchor="w")
        self.tree.heading("phone", text="전화번호", anchor="w")
        self.tree.heading("company", text="회사", anchor="w")
        self.tree.heading("birthday", text="🎂 생일", anchor="center")
        self.tree.heading("memo", text="메모", anchor="w")

        self.tree.column("check", width=36, minwidth=30, stretch=False, anchor="center")
        self.tree.column("no", width=40, minwidth=35, stretch=False, anchor="center")
        self.tree.column("name", width=100, minwidth=80)
        self.tree.column("category", width=80, minwidth=60)
        self.tree.column("phone", width=130, minwidth=100)
        self.tree.column("company", width=120, minwidth=80)
        self.tree.column("birthday", width=64, minwidth=54, stretch=False, anchor="center")
        self.tree.column("memo", width=180, minwidth=90)

        # 스크롤바
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 클릭: check 컬럼이면 토글, 아니면 일반 동작
        self.tree.bind("<Button-1>", self._on_tree_click)
        # 더블클릭 → 편집
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        # 우클릭 → 메뉴
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        # contact id → tree item 매핑
        self._tree_id_map = {}
        # 체크박스 영구 선택 — contact_id 집합
        self._checked_ids = set()

        # -- 하단: 카운트 + 선택 삭제 --
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=24, pady=(0, 12))

        self.count_label = ctk.CTkLabel(
            bottom, text="총 0명",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        )
        self.count_label.pack(side="left")

        ctk.CTkButton(
            bottom, text="🗑️ 선택 삭제", width=100, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color="#c0392b", hover_color="#a93226",
            text_color="white", corner_radius=6,
            command=self._delete_selected
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            bottom, text="✏️ 편집", width=80, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self._edit_selected
        ).pack(side="right", padx=(4, 0))

        # 선택 → 카테고리 이동
        ctk.CTkLabel(
            bottom, text="선택 →",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        ).pack(side="right", padx=(0, 4))

        self.move_cat_var = ctk.StringVar(value="이동할 카테고리")
        self.move_cat_menu = ctk.CTkOptionMenu(
            bottom, values=["friend", "family", "business", "vip", "other"],
            variable=self.move_cat_var,
            width=120, height=28,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self._move_selected_to_category
        )
        self.move_cat_menu.pack(side="right", padx=(0, 8))

        self.refresh_list()

    def _refresh_category_buttons(self):
        """카테고리 버튼 동적 생성 + 이동 드롭다운 갱신"""
        for w in self.cat_btn_frame.winfo_children():
            w.destroy()

        categories = [("all", "전체")]
        if self.orchestrator:
            for cat in self.orchestrator.contact_mgr.get_all_categories():
                cat_label = {
                    "friend": "친구", "family": "가족", "business": "사업체",
                    "vip": "VIP", "other": "기타"
                }.get(cat, cat)
                categories.append((cat, cat_label))
        else:
            for cat, label in [("friend", "친구"), ("family", "가족"),
                               ("business", "사업체"), ("vip", "VIP"), ("other", "기타")]:
                categories.append((cat, label))

        current = self.category_var.get()
        # DEFAULT_CATEGORIES 는 삭제 불가 (보호)
        from core.contact_manager import ContactManager
        # 보호: 전체(all) + 카카오(kakao_friend) 만. 나머지는 모두 삭제 가능.
        protected_cats = {"all", "kakao_friend"}

        for cat_id, cat_name in categories:
            is_active = cat_id == current
            btn = ctk.CTkButton(
                self.cat_btn_frame, text=cat_name, width=70, height=28,
                font=(T.get_font_family(), T.FONT_SIZE_SMALL),
                fg_color=T.ACCENT if is_active else T.BG_HOVER,
                hover_color=T.ACCENT_HOVER if is_active else T.BORDER,
                text_color=T.TEXT_ON_ACCENT if is_active else T.TEXT_SECONDARY,
                corner_radius=14,
                command=lambda cid=cat_id: self._filter_category(cid)
            )
            btn.pack(side="left", padx=(0, 4))

            # 우클릭 메뉴: 커스텀 카테고리 삭제 (기본 카테고리는 보호)
            # CTkButton 은 내부 Canvas/Label 자식이 이벤트 가로채서 → 재귀 바인딩 필요
            if cat_id not in protected_cats:
                handler = (
                    lambda e, cid=cat_id, cname=cat_name:
                    self._on_category_right_click(e, cid, cname)
                )
                self._bind_right_click_recursive(btn, handler)

        # 이동 드롭다운 카테고리 갱신
        if hasattr(self, 'move_cat_menu') and self.orchestrator:
            all_cats = self.orchestrator.contact_mgr.get_all_categories()
            self.move_cat_menu.configure(values=all_cats)

    def refresh_list(self, category: str = "all", search: str = ""):
        """연락처 목록 새로고침 (Treeview - 즉시 로드)"""
        # 기존 항목 전부 삭제
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._tree_id_map.clear()

        cat_label_map = {
            "friend": "친구", "family": "가족", "business": "사업체",
            "vip": "VIP", "other": "기타", "미지정": "미지정"
        }

        if self.api_client and self.api_client.is_logged_in:
            try:
                cat = category if category != "all" else None
                self._contacts_cache = self.api_client.get_contacts(
                    category=cat, search=search if search else None
                )
            except Exception:
                self._contacts_cache = []
            for idx, c in enumerate(self._contacts_cache, 1):
                cat_text = cat_label_map.get(c.get("category", ""), c.get("category", ""))
                cid = c.get("id", "")
                check_mark = "☑" if cid in self._checked_ids else "☐"
                iid = self.tree.insert("", 0, values=(
                    check_mark, idx, c.get("name", ""), cat_text,
                    c.get("phone", ""), c.get("company", ""),
                    c.get("birthday", ""),
                    c.get("memo", "")[:30]
                ))
                self._tree_id_map[iid] = cid
            self.count_label.configure(text=f"총 {len(self._contacts_cache)}명")
        elif self.orchestrator:
            contacts = self.orchestrator.contact_mgr.get_by_category(category)
            if search:
                s = search.lower().strip()
                import re as _re
                month_mm = None
                m = _re.match(r"(\d{1,2})\s*월$", s)
                if m:
                    month_mm = f"{int(m.group(1)):02d}"

                def _match(c):
                    b = c.birthday or ""
                    if (s in c.name.lower() or s in c.company.lower()
                            or s in (c.memo or "").lower() or (s and s in b)):
                        return True
                    return bool(month_mm and b[:2] == month_mm)
                contacts = [c for c in contacts if _match(c)]
            # 최근 추가 순 (최신이 위) → insert at index 0이 아닌 "end"로 역순 삽입
            for idx, contact in enumerate(reversed(contacts), 1):
                cat_text = cat_label_map.get(contact.category, contact.category)
                check_mark = "☑" if contact.id in self._checked_ids else "☐"
                iid = self.tree.insert("", "end", values=(
                    check_mark, idx, contact.name, cat_text,
                    contact.phone or "", contact.company or "",
                    contact.birthday or "",
                    (contact.memo or "")[:30]
                ))
                self._tree_id_map[iid] = contact.id
            self.count_label.configure(text=f"총 {len(contacts)}명")

    # -- Treeview 이벤트 --

    def _get_contact_by_tree_item(self, iid):
        """Treeview item → Contact 객체"""
        contact_id = self._tree_id_map.get(iid)
        if contact_id and self.orchestrator:
            for c in self.orchestrator.contact_mgr.get_all():
                if c.id == contact_id:
                    return c
        return None

    def _on_tree_click(self, event):
        """단일 클릭 — check 컬럼이면 토글, 그 외엔 기본 동작 통과"""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        if col != "#1":  # check 컬럼이 아니면 통과
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return

        cid = self._tree_id_map.get(iid)
        if not cid:
            return

        # 토글
        if cid in self._checked_ids:
            self._checked_ids.discard(cid)
            new_mark = "☐"
        else:
            self._checked_ids.add(cid)
            new_mark = "☑"

        # 해당 행 첫 컬럼 (check) 만 갱신 — 깜빡임 방지
        values = list(self.tree.item(iid, "values"))
        values[0] = new_mark
        self.tree.item(iid, values=values)

        # 헤더 표시 갱신
        self._update_check_header()
        return "break"  # 기본 selection 동작 차단

    def _toggle_all_check(self):
        """헤더 ☐ 클릭 — 현재 보이는 모든 행 전체선택/해제 토글"""
        all_iids = self.tree.get_children()
        all_cids = [self._tree_id_map.get(i) for i in all_iids]
        all_cids = [c for c in all_cids if c]

        # 모두 체크돼있으면 해제, 아니면 모두 체크
        all_checked = all(c in self._checked_ids for c in all_cids) if all_cids else False
        if all_checked:
            for c in all_cids:
                self._checked_ids.discard(c)
            new_mark = "☐"
        else:
            self._checked_ids.update(all_cids)
            new_mark = "☑"

        # 모든 행 첫 컬럼 갱신
        for iid in all_iids:
            values = list(self.tree.item(iid, "values"))
            if values:
                values[0] = new_mark
                self.tree.item(iid, values=values)
        self._update_check_header()

    def _update_check_header(self):
        """헤더 체크 표시 갱신 (전체선택 상태에 따라)"""
        all_iids = self.tree.get_children()
        all_cids = [self._tree_id_map.get(i) for i in all_iids]
        all_cids = [c for c in all_cids if c]
        if not all_cids:
            self.tree.heading("check", text="☐")
            return
        n_checked = sum(1 for c in all_cids if c in self._checked_ids)
        if n_checked == 0:
            self.tree.heading("check", text="☐")
        elif n_checked == len(all_cids):
            self.tree.heading("check", text="☑")
        else:
            self.tree.heading("check", text="◧")  # 일부 선택

    def _get_target_ids(self) -> list:
        """삭제/이동 대상 ID — 체크박스 선택 우선, 없으면 tree.selection()"""
        if self._checked_ids:
            return [c for c in self._checked_ids]
        # 체크박스 비어있으면 tree 선택 사용
        sel = self.tree.selection()
        return [self._tree_id_map.get(iid) for iid in sel
                if self._tree_id_map.get(iid)]

    def _on_tree_double_click(self, event):
        """더블클릭 → 편집"""
        # check 컬럼 더블클릭은 무시 (단일 클릭 토글로 처리됨)
        col = self.tree.identify_column(event.x)
        if col == "#1":
            return
        sel = self.tree.selection()
        if not sel:
            return
        contact = self._get_contact_by_tree_item(sel[0])
        if contact:
            self._edit_contact(contact)

    def _on_tree_right_click(self, event):
        """우클릭 → 컨텍스트 메뉴"""
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        contact = self._get_contact_by_tree_item(iid)
        if not contact:
            return

        menu = tk.Menu(self, tearoff=0, bg="#2d333b", fg="#e6edf3",
                       activebackground="#2f81f7", activeforeground="#fff")
        menu.add_command(label=f"편집: {contact.name}", command=lambda: self._edit_contact(contact))
        menu.add_separator()

        # 카테고리 변경 서브메뉴
        cat_menu = tk.Menu(menu, tearoff=0, bg="#2d333b", fg="#e6edf3",
                           activebackground="#2f81f7", activeforeground="#fff")
        all_cats = self.orchestrator.contact_mgr.get_all_categories() if self.orchestrator else []
        for cat in all_cats:
            cat_menu.add_command(
                label=cat,
                command=lambda c=contact, ca=cat: self._quick_change_category(c.id, ca)
            )
        menu.add_cascade(label="카테고리 변경", menu=cat_menu)
        menu.add_separator()
        menu.add_command(label="삭제", command=lambda: self._delete_contact(contact.id))
        menu.tk_popup(event.x_root, event.y_root)

    def _edit_selected(self):
        """선택된 연락처 1명 편집 (여러 명 선택 시 첫 번째)"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("알림", "편집할 연락처를 1명 선택하세요.\n"
                                          "팁: 더블클릭 또는 우클릭으로도 편집 가능합니다.")
            return
        if not self.orchestrator:
            return
        cid = self._tree_id_map.get(sel[0])
        if not cid:
            return
        contact = next((c for c in self.orchestrator.contact_mgr.get_all()
                         if c.id == cid), None)
        if contact:
            self._edit_contact(contact)

    def _delete_selected(self):
        """체크박스 선택 (또는 행 선택) 연락처 일괄 삭제"""
        cids = self._get_target_ids()
        if not cids:
            messagebox.showinfo(
                "알림",
                "삭제할 연락처를 선택하세요.\n"
                "• 좌측 ☐ 체크박스 클릭 (다중선택)\n"
                "• 또는 행 클릭 (단일선택)"
            )
            return
        if not messagebox.askyesno(
            "삭제 확인",
            f"{len(cids)}명의 연락처를 삭제하시겠습니까?\n"
            f"(이 작업은 되돌릴 수 없습니다)"
        ):
            return
        if self.orchestrator:
            for cid in cids:
                self.orchestrator.contact_mgr.delete(cid)
            # 체크 상태 클리어 (삭제됐으니까)
            self._checked_ids -= set(cids)
        self.refresh_list(category=self.category_var.get())

    def _quick_change_category(self, contact_id, new_category):
        """카테고리 즉시 변경"""
        if self.orchestrator:
            self.orchestrator.contact_mgr.update(contact_id, category=new_category)
            self._refresh_category_buttons()
            self.refresh_list(category=self.category_var.get())

    def _move_selected_to_category(self, new_category):
        """선택된 연락처를 다른 카테고리로 일괄 이동"""
        cids = self._get_target_ids()
        if not cids:
            messagebox.showinfo(
                "알림",
                "이동할 연락처를 선택하세요.\n"
                "• 좌측 ☐ 체크박스 클릭 (다중선택)\n"
                "• 또는 행 클릭"
            )
            self.move_cat_var.set("이동할 카테고리")
            return

        cat_label_map = {
            "friend": "친구", "family": "가족", "business": "사업체",
            "vip": "VIP", "other": "기타", "kakao_friend": "카톡친구"
        }
        label = cat_label_map.get(new_category, new_category)

        if not messagebox.askyesno("카테고리 이동",
                                    f"{len(cids)}명을 '{label}'(으)로 이동하시겠습니까?"):
            self.move_cat_var.set("이동할 카테고리")
            return

        if self.orchestrator:
            self.orchestrator.contact_mgr.batch_update_category(cids, new_category)
            # 이동 후 체크 클리어 (다른 카테고리로 갔으니)
            self._checked_ids -= set(cids)

        self.move_cat_var.set("이동할 카테고리")
        self._refresh_category_buttons()
        self.refresh_list(category=self.category_var.get())

    def _filter_category(self, category: str):
        self.category_var.set(category)
        self._refresh_category_buttons()
        self.refresh_list(category=category, search=self.search_entry.get())

    def _on_search(self):
        self.refresh_list(
            category=self.category_var.get(),
            search=self.search_entry.get()
        )

    def _filter_birthday_today(self):
        """오늘 생일자 — 검색창에 오늘 날짜(MM-DD) 넣어 필터."""
        from datetime import datetime
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, datetime.now().strftime("%m-%d"))
        self._on_search()

    def _filter_birthday_month(self):
        """이번 달 생일자 — 검색창에 'N월' 넣어 필터."""
        from datetime import datetime
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, f"{datetime.now().month}월")
        self._on_search()

    def _add_contact(self):
        if self.api_client and self.api_client.is_logged_in:
            dialog = ContactDialogAPI(self, title="연락처 추가")
            self.wait_window(dialog)
            if dialog.result:
                try:
                    self.api_client.create_contact(dialog.result)
                    self._refresh_category_buttons()
                    self.refresh_list(category=self.category_var.get())
                except Exception as e:
                    messagebox.showerror("오류", str(e))
            return

        # 현재 보고 있는 카테고리를 기본값으로 전달
        current_cat = self.category_var.get()
        default_cat = current_cat if current_cat != "all" else "other"
        dialog = ContactDialog(self, title="연락처 추가", orchestrator=self.orchestrator,
                               default_category=default_cat)
        self.wait_window(dialog)
        if dialog.result and self.orchestrator:
            from core.contact_manager import Contact
            contact = Contact(**dialog.result)
            if self.orchestrator.contact_mgr.add(contact):
                self._refresh_category_buttons()
                self.refresh_list(category=self.category_var.get())
            else:
                messagebox.showwarning("중복", "동일한 이름과 카테고리의 연락처가 이미 있습니다.")

    def _edit_contact(self, contact):
        dialog = ContactDialog(self, title="연락처 편집", contact=contact,
                               orchestrator=self.orchestrator)
        self.wait_window(dialog)
        if dialog.result and self.orchestrator:
            self.orchestrator.contact_mgr.update(contact.id, **dialog.result)
            self._refresh_category_buttons()
            self.refresh_list(category=self.category_var.get())

    def _delete_contact(self, contact_id):
        if messagebox.askyesno("삭제 확인", "정말 삭제하시겠습니까?"):
            if self.orchestrator:
                self.orchestrator.contact_mgr.delete(contact_id)
                self.refresh_list(category=self.category_var.get())

    def _add_category(self):
        dialog = CategoryDialog(self, orchestrator=self.orchestrator)
        self.wait_window(dialog)
        if dialog.result and self.orchestrator:
            if self.orchestrator.contact_mgr.add_category(dialog.result):
                self._refresh_category_buttons()
            else:
                messagebox.showwarning("중복", "이미 존재하는 카테고리입니다.")

    def _bind_right_click_recursive(self, widget, handler):
        """CTkButton 자식 (Canvas, Label 등) 까지 우클릭 이벤트 전파.

        CTk 위젯은 wrapper 라 외부 frame 에만 bind 하면 자식이 가로채서
        이벤트가 도달하지 못한다. 재귀로 모든 자식에 같은 핸들러 등록.
        """
        widget.bind("<Button-3>", handler)
        for child in widget.winfo_children():
            self._bind_right_click_recursive(child, handler)

    def _on_category_right_click(self, event, cat_id: str, cat_name: str):
        """카테고리 버튼 우클릭 → 삭제 메뉴 (커스텀 카테고리 한정)"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=f"🗑️ '{cat_name}' 카테고리 삭제",
            command=lambda: self._delete_category(cat_id, cat_name),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _delete_category(self, cat_id: str, cat_name: str):
        """카테고리 삭제 — 안에 친구 있으면 경고."""
        if not self.orchestrator:
            return

        # 카테고리 안에 있는 친구 수 확인
        contacts_in_cat = self.orchestrator.contact_mgr.get_by_category(cat_id)
        n = len(contacts_in_cat)

        if n > 0:
            confirm = messagebox.askyesno(
                "⚠️ 카테고리 삭제 경고",
                f"카테고리 '{cat_name}' 에 연락처 {n}명이 포함되어 있습니다.\n\n"
                f"카테고리를 삭제해도 연락처는 그대로 유지되지만,\n"
                f"이 카테고리로 분류된 채로 남게 됩니다.\n\n"
                f"💡 권장: 먼저 연락처를 다른 카테고리로 옮기거나 삭제한 후\n"
                f"   카테고리를 삭제하세요.\n\n"
                f"그래도 삭제할까요?"
            )
            if not confirm:
                return
        else:
            confirm = messagebox.askyesno(
                "카테고리 삭제 확인",
                f"카테고리 '{cat_name}' 을(를) 삭제할까요?"
            )
            if not confirm:
                return

        if self.orchestrator.contact_mgr.delete_category(cat_id):
            messagebox.showinfo("삭제 완료", f"'{cat_name}' 카테고리가 삭제되었습니다.")
            # 현재 보고 있는 카테고리가 삭제됐으면 'all' 로 전환
            if self.category_var.get() == cat_id:
                self.category_var.set("all")
            self._refresh_category_buttons()
            self.refresh_list(category=self.category_var.get())
        else:
            messagebox.showerror(
                "삭제 실패",
                "카테고리를 삭제할 수 없습니다.\n"
                "(기본 카테고리는 보호됨)"
            )

    def _download_sample(self):
        filepath = filedialog.asksaveasfilename(
            title="샘플 엑셀 저장",
            defaultextension=".xlsx",
            initialfile="연락처_샘플.xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if filepath and self.orchestrator:
            try:
                self.orchestrator.contact_mgr.create_sample_excel(filepath)
                messagebox.showinfo("다운로드 완료",
                                    f"샘플 파일 저장 완료!\n{filepath}\n\n"
                                    "이 파일을 수정한 후 '가져오기'로 업로드하세요.")
            except Exception as e:
                messagebox.showerror("오류", str(e))

    def _import_excel(self):
        filepath = filedialog.askopenfilename(
            title="연락처 파일 선택 (Excel / VCF)",
            filetypes=[
                ("연락처 파일", "*.xlsx *.xls *.vcf"),
                ("Excel", "*.xlsx *.xls"),
                ("vCard (VCF)", "*.vcf"),
            ]
        )
        if not filepath:
            return

        ext = os.path.splitext(filepath)[1].lower()

        if self.api_client and self.api_client.is_logged_in:
            if ext == ".vcf":
                messagebox.showwarning(
                    "지원되지 않음",
                    "VCF 가져오기는 로컬 모드에서만 지원됩니다.\n"
                    "엑셀 파일로 변환해서 업로드해주세요."
                )
                return
            try:
                result = self.api_client.import_contacts(filepath)
                messagebox.showinfo("가져오기 완료", f"추가: {result.get('added', 0)}명")
                self.refresh_list(category=self.category_var.get())
            except Exception as e:
                messagebox.showerror("오류", str(e))
        elif self.orchestrator:
            current_cat = self.category_var.get()
            default_cat = current_cat if current_cat != "all" else None

            if ext == ".vcf":
                result = self.orchestrator.contact_mgr.import_from_vcf(
                    filepath, default_category=default_cat
                )
                src_label = "VCF"
            else:
                result = self.orchestrator.contact_mgr.import_from_excel(
                    filepath, default_category=default_cat
                )
                src_label = "엑셀"

            cat_msg = f"\n카테고리 미지정 → '{default_cat}' 자동 지정" if default_cat else ""
            err_msg = ""
            if result.get("errors"):
                preview = "\n".join(result["errors"][:3])
                err_msg = f"\n\n오류 {len(result['errors'])}건:\n{preview}"
            messagebox.showinfo(
                "가져오기 완료",
                f"[{src_label}] 추가: {result['success']}명\n"
                f"건너뜀: {result['skipped']}명{cat_msg}{err_msg}"
            )
            self._refresh_category_buttons()
            self.refresh_list(category=self.category_var.get())

    def _sync_kakao_friends(self):
        """카톡 친구목록 라이브 동기화 — 백그라운드 스레드 + 진행 다이얼로그."""
        if not self.orchestrator:
            messagebox.showwarning("미지원", "이 기능은 로컬 모드에서만 지원됩니다.")
            return

        confirm = KakaoSyncConfirmDialog(self)
        self.wait_window(confirm)
        if not confirm.proceed:
            return

        # 카톡친구 카테고리로 자동 전환
        self.category_var.set("kakao_friend")
        self._refresh_category_buttons()
        self.refresh_list(category="kakao_friend")

        # 진행 다이얼로그 띄우고 백그라운드 스레드 시작
        dialog = KakaoFriendsSyncDialog(self, self.orchestrator,
                                         on_done=self._on_sync_done)
        dialog.start()

    def _on_sync_done(self, result: dict):
        """동기화 완료 콜백 — 카테고리 버튼/리스트 갱신"""
        self._refresh_category_buttons()
        self.refresh_list(category=self.category_var.get())

    def _export_excel(self):
        filepath = filedialog.asksaveasfilename(
            title="엑셀 저장",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not filepath:
            return

        if self.api_client and self.api_client.is_logged_in:
            try:
                self.api_client.export_contacts(filepath)
                messagebox.showinfo("내보내기 완료", f"저장 완료: {filepath}")
            except Exception as e:
                messagebox.showerror("오류", str(e))
        elif self.orchestrator:
            self.orchestrator.contact_mgr.export_to_excel(filepath)
            messagebox.showinfo("내보내기 완료", f"저장 완료: {filepath}")


class CategoryDialog(ctk.CTkToplevel):
    """카테고리 추가 다이얼로그"""

    def __init__(self, parent, orchestrator=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("카테고리 추가")
        self.geometry("350x200")
        self.configure(fg_color=T.BG_DARK)
        self.result = None
        self.orchestrator = orchestrator
        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="새 카테고리 이름",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(padx=24, pady=(24, 8), anchor="w")

        self.entry = ctk.CTkEntry(
            self, placeholder_text="예: 동호회, 학교, 교회...",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=40, corner_radius=6
        )
        self.entry.pack(fill="x", padx=24)
        self.entry.focus()

        if self.orchestrator:
            existing = self.orchestrator.contact_mgr.get_all_categories()
            ctk.CTkLabel(
                self, text=f"기존: {', '.join(existing)}",
                font=(T.get_font_family(), 9),
                text_color=T.TEXT_MUTED, wraplength=300
            ).pack(padx=24, pady=(4, 0), anchor="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=16)

        ctk.CTkButton(
            btn_frame, text="취소", width=100, height=36,
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="추가", width=100, height=36,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, corner_radius=6,
            command=self._save
        ).pack(side="right")

    def _save(self):
        name = self.entry.get().strip()
        if not name:
            messagebox.showwarning("필수 입력", "카테고리 이름을 입력해주세요.")
            return
        self.result = name
        self.destroy()


class ContactDialog(ctk.CTkToplevel):
    """연락처 추가/편집 다이얼로그"""

    def __init__(self, parent, title="연락처", contact=None, orchestrator=None,
                 default_category=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title(title)
        self.geometry("480x720")
        self.configure(fg_color=T.BG_DARK)
        self.result = None
        self.contact = contact
        self.orchestrator = orchestrator
        self.default_category = default_category

        self.transient(parent)
        self.grab_set()

        # 부모 창 가운데 위치
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - 480) // 2
            y = py + (ph - 720) // 2
            self.geometry(f"480x720+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

        self._build()

    def _build(self):
        # ── 헤더 ──
        is_edit = self.contact is not None
        header_text = "✏️  연락처 편집" if is_edit else "📇  새 연락처 추가"
        ctk.CTkLabel(
            self, text=header_text,
            font=(T.get_font_family(), 18, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(pady=(20, 14))

        # ── 본문 카드 ──
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=T.BG_CARD, corner_radius=8,
            scrollbar_button_color=T.BG_HOVER
        )
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        fields = [
            ("이름 *", "name"),
            ("전화번호", "phone"),
            ("회사", "company"),
            ("직급", "position"),
            ("메모", "memo"),
        ]

        self.entries = {}

        for label_text, field_name in fields:
            ctk.CTkLabel(
                scroll, text=label_text,
                font=(T.get_font_family(), T.FONT_SIZE_SMALL),
                text_color=T.TEXT_SECONDARY
            ).pack(padx=20, pady=(12, 4), anchor="w")

            entry = ctk.CTkEntry(
                scroll, font=(T.get_font_family(), T.FONT_SIZE_BODY),
                fg_color=T.BG_INPUT, border_color=T.BORDER,
                text_color=T.TEXT_PRIMARY, height=36, corner_radius=6
            )
            entry.pack(fill="x", padx=20)
            self.entries[field_name] = entry

            if self.contact and hasattr(self.contact, field_name):
                entry.insert(0, getattr(self.contact, field_name) or "")

        # 생일 / 기념일
        date_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        date_frame.pack(fill="x", padx=20, pady=(12, 0))

        # 생일
        bd_frame = ctk.CTkFrame(date_frame, fg_color="transparent")
        bd_frame.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(
            bd_frame, text="생일 (MM-DD)",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_SECONDARY
        ).pack(anchor="w")
        bd_entry = ctk.CTkEntry(
            bd_frame, placeholder_text="예: 03-15",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6
        )
        bd_entry.pack(fill="x")
        self.entries["birthday"] = bd_entry
        if self.contact and self.contact.birthday:
            bd_entry.insert(0, self.contact.birthday)

        # 기념일
        an_frame = ctk.CTkFrame(date_frame, fg_color="transparent")
        an_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            an_frame, text="기념일 (MM-DD)",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_SECONDARY
        ).pack(anchor="w")
        an_entry = ctk.CTkEntry(
            an_frame, placeholder_text="예: 05-10",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6
        )
        an_entry.pack(fill="x")
        self.entries["anniversary"] = an_entry
        if self.contact and self.contact.anniversary:
            an_entry.insert(0, self.contact.anniversary)

        # 카테고리 선택 (동적 목록)
        ctk.CTkLabel(
            scroll, text="카테고리",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_SECONDARY
        ).pack(padx=20, pady=(12, 4), anchor="w")

        categories = ["friend", "family", "business", "vip", "other"]
        if self.orchestrator:
            categories = self.orchestrator.contact_mgr.get_all_categories()

        default_cat = self.contact.category if self.contact else (self.default_category or "other")
        self.category_var = ctk.StringVar(value=default_cat)
        self.category_menu = ctk.CTkOptionMenu(
            scroll, values=categories,
            variable=self.category_var,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6
        )
        self.category_menu.pack(fill="x", padx=20, pady=(0, 16))

        # 버튼
        btn_frame = ctk.CTkFrame(self, fg_color="transparent", height=70)
        btn_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        btn_frame.pack_propagate(False)

        ctk.CTkButton(
            btn_frame, text="취소", width=120,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=40, corner_radius=6,
            command=self.destroy
        ).pack(side="left", pady=15)

        ctk.CTkButton(
            btn_frame, text="저장하기", width=120,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, height=40, corner_radius=6,
            command=self._save
        ).pack(side="right", pady=15)

    def _save(self):
        name = self.entries["name"].get().strip()
        if not name:
            messagebox.showwarning("필수 입력", "이름을 입력해주세요.")
            return

        self.result = {
            "name": name,
            "phone": self.entries["phone"].get().strip(),
            "company": self.entries["company"].get().strip(),
            "position": self.entries["position"].get().strip(),
            "memo": self.entries["memo"].get().strip(),
            "birthday": self.entries["birthday"].get().strip(),
            "anniversary": self.entries["anniversary"].get().strip(),
            "category": self.category_var.get()
        }
        self.destroy()


class ContactDialogAPI(ctk.CTkToplevel):
    """API용 연락처 추가/편집 다이얼로그 (SaaS 모드)"""

    def __init__(self, parent, title="연락처", contact_data=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title(title)
        self.geometry("420x520")
        self.configure(fg_color=T.BG_DARK)
        self.result = None
        self.contact_data = contact_data or {}
        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        fields = [
            ("이름 *", "name"), ("전화번호", "phone"), ("회사", "company"),
            ("직급", "position"), ("메모", "memo"), ("생일 (MM-DD)", "birthday"),
            ("기념일 (MM-DD)", "anniversary"),
        ]
        self.entries = {}

        for label_text, field_name in fields:
            ctk.CTkLabel(scroll, text=label_text,
                         font=(T.get_font_family(), T.FONT_SIZE_SMALL),
                         text_color=T.TEXT_SECONDARY).pack(padx=24, pady=(8, 2), anchor="w")
            entry = ctk.CTkEntry(scroll, font=(T.get_font_family(), T.FONT_SIZE_BODY),
                                 fg_color=T.BG_INPUT, border_color=T.BORDER,
                                 text_color=T.TEXT_PRIMARY, height=36, corner_radius=6)
            entry.pack(fill="x", padx=24)
            self.entries[field_name] = entry
            val = self.contact_data.get(field_name, "")
            if val:
                entry.insert(0, val)

        # 카테고리
        ctk.CTkLabel(scroll, text="카테고리",
                     font=(T.get_font_family(), T.FONT_SIZE_SMALL),
                     text_color=T.TEXT_SECONDARY).pack(padx=24, pady=(8, 2), anchor="w")
        categories = ["customer", "friend", "family", "business", "vip", "other"]
        self.category_var = ctk.StringVar(value=self.contact_data.get("category", "other"))
        ctk.CTkOptionMenu(scroll, values=categories, variable=self.category_var,
                          font=(T.get_font_family(), T.FONT_SIZE_BODY),
                          fg_color=T.BG_INPUT, text_color=T.TEXT_PRIMARY,
                          height=36, corner_radius=6).pack(fill="x", padx=24)

        # 버튼
        btn_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD, height=60)
        btn_frame.pack(fill="x", side="bottom")
        btn_frame.pack_propagate(False)
        ctk.CTkButton(btn_frame, text="취소", width=100, fg_color=T.BG_HOVER,
                      hover_color=T.BORDER, text_color=T.TEXT_PRIMARY, height=36,
                      command=self.destroy).pack(side="left", padx=24, pady=12)
        ctk.CTkButton(btn_frame, text="저장", width=100, fg_color=T.ACCENT,
                      hover_color=T.ACCENT_HOVER, text_color=T.TEXT_ON_ACCENT, height=36,
                      command=self._save).pack(side="right", padx=24, pady=12)

    def _save(self):
        name = self.entries["name"].get().strip()
        if not name:
            messagebox.showwarning("필수 입력", "이름을 입력해주세요.")
            return
        self.result = {
            "name": name,
            "phone": self.entries["phone"].get().strip(),
            "company": self.entries["company"].get().strip(),
            "position": self.entries["position"].get().strip(),
            "memo": self.entries["memo"].get().strip(),
            "birthday": self.entries["birthday"].get().strip(),
            "anniversary": self.entries["anniversary"].get().strip(),
            "category": self.category_var.get()
        }
        self.destroy()


class KakaoSyncConfirmDialog(ctk.CTkToplevel):
    """카톡 친구 자동 수집 시작 전 확인 다이얼로그.

    KakaoFriendsSyncDialog 와 시각 톤 통일 — 헤더 + 노란 경고카드 + 액션 버튼.
    `proceed` 속성으로 결과 전달 (True=시작, False=취소).
    """

    WIDTH = 480
    HEIGHT = 460

    def __init__(self, parent):
        super().__init__(parent)
        self.proceed = False

        self.title("카톡 친구 자동 수집")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.configure(fg_color=T.BG_DARK)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            x = px + (pw - self.WIDTH) // 2
            y = py + (ph - self.HEIGHT) // 2
            self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

        self._build()

    def _build(self):
        # ── 헤더 ──
        ctk.CTkLabel(
            self, text="🔄 카톡 친구 자동 수집",
            font=(T.get_font_family(), 18, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(pady=(20, 6))

        ctk.CTkLabel(
            self,
            text="카톡 친구탭을 ↓ 키로 스크롤하며 이름을 자동 수집합니다.",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY,
            wraplength=440, justify="center",
        ).pack(pady=(0, 14), padx=20)

        # ── 필수 조건 카드 (노란 경고) ──
        warn_card = ctk.CTkFrame(
            self, fg_color="#3a2818", corner_radius=8,
            border_width=1, border_color="#f0b90b",
        )
        warn_card.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            warn_card, text="⚠️  필수 조건",
            font=(T.get_font_family(), 13, "bold"),
            text_color="#f0b90b",
        ).pack(padx=14, pady=(10, 4), anchor="w")

        ctk.CTkLabel(
            warn_card,
            text=(
                "• 카카오톡 PC 가 친구탭 활성 상태\n"
                "• 수집 중 PC 사용 자제 (자동 조작)"
            ),
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_PRIMARY,
            justify="left",
        ).pack(padx=14, pady=(0, 12), anchor="w")

        # ── 안내 카드 (저장/중단) ──
        info_card = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=8)
        info_card.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkLabel(
            info_card,
            text=(
                "📥  수집된 이름은 'kakao_friend' 카테고리에 즉시 저장됩니다.\n"
                "⏸️  중간에 멈추려면 진행창의 '중단 + 저장' 버튼을 누르세요."
            ),
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY,
            justify="left", wraplength=420,
        ).pack(padx=14, pady=12, anchor="w")

        # ── 버튼 ──
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="취소", width=140, height=40,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=6,
            command=self._cancel,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="✅  수집 시작", width=140, height=40,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, corner_radius=6,
            command=self._confirm,
        ).pack(side="right")

    def _confirm(self):
        self.proceed = True
        self.destroy()

    def _cancel(self):
        self.proceed = False
        self.destroy()


class KakaoFriendsSyncDialog(ctk.CTkToplevel):
    """
    카톡 친구 라이브 동기화 진행 다이얼로그.
    - 별도 스레드로 collect_friends 실행
    - 콜백마다 self.after(0, ...) 로 UI 갱신
    - 중단/저장 버튼
    """

    def __init__(self, parent, orchestrator, on_done=None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.on_done = on_done
        self._stop_flag = False
        self._thread = None
        self._result = None
        self._added = 0
        self._dup = 0
        self._fail = 0

        self.title("카톡 친구 동기화")
        self.geometry("520x680")
        self.configure(fg_color=T.BG_DARK)
        self.transient(parent)
        self.grab_set()
        # 부모 창 가운데로 위치
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - 520) // 2
            y = py + (ph - 680) // 2
            self.geometry(f"520x680+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

        self._build()

    def _build(self):
        # ── 헤더 ──
        ctk.CTkLabel(
            self, text="🔄 카톡 친구 자동 수집",
            font=(T.get_font_family(), 18, "bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(pady=(20, 6))

        self.status_label = ctk.CTkLabel(
            self, text="시작 준비 중...",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color="#f0b90b",  # 진행중 = 노란빛 강조
            wraplength=480,
        )
        self.status_label.pack(pady=(0, 10), padx=20)

        # ── 안내 문구 카드 (잘 보이게) ──
        warn_card = ctk.CTkFrame(
            self, fg_color="#3a2818", corner_radius=8,
            border_width=1, border_color="#f0b90b",
        )
        warn_card.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(
            warn_card,
            text="⚠️  자동 조작 중에는 카톡/마우스/키보드 사용을 자제해주세요.",
            font=(T.get_font_family(), 12, "bold"),
            text_color="#f0b90b",
            wraplength=460, justify="left",
        ).pack(padx=12, pady=10)

        # ── 카운터 ──
        counter_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=8)
        counter_frame.pack(fill="x", padx=20, pady=(0, 12))

        self.added_label = ctk.CTkLabel(
            counter_frame, text="✓ 추가: 0",
            font=(T.get_font_family(), 14, "bold"),
            text_color="#3fb950",
        )
        self.added_label.pack(side="left", padx=14, pady=10)

        self.dup_label = ctk.CTkLabel(
            counter_frame, text="· 중복: 0",
            font=(T.get_font_family(), 14),
            text_color=T.TEXT_SECONDARY,
        )
        self.dup_label.pack(side="left", padx=14, pady=10)

        self.fail_label = ctk.CTkLabel(
            counter_frame, text="× OCR실패: 0",
            font=(T.get_font_family(), 14),
            text_color="#c0392b",
        )
        self.fail_label.pack(side="left", padx=14, pady=10)

        # ── 라이브 추가 목록 ──
        ctk.CTkLabel(
            self, text="📝 실시간 추가 목록",
            font=(T.get_font_family(), 12, "bold"),
            text_color=T.TEXT_SECONDARY,
        ).pack(anchor="w", padx=22, pady=(4, 4))

        self.list_box = ctk.CTkTextbox(
            self, height=380,
            fg_color=T.BG_INPUT, text_color=T.TEXT_PRIMARY,
            font=(T.get_font_family(), 12),
            corner_radius=8,
            border_width=1, border_color=T.BORDER,
        )
        self.list_box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self.list_box.configure(state="disabled")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="🛑 중단 + 저장",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            fg_color="#c0392b", hover_color="#a93226",
            text_color="white", height=36, corner_radius=6,
            command=self._on_stop,
        )
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.close_btn = ctk.CTkButton(
            btn_frame, text="닫기",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6,
            state="disabled",
            command=self._on_close,
        )
        self.close_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def start(self):
        """동기화 시작 — 먼저 PaddleOCR pre-load 후 워커 스레드 가동"""
        import threading

        self.status_label.configure(text="🔧 OCR 엔진 초기화 중... (3~5초)")
        self.update_idletasks()

        def preinit():
            """무거운 PaddleOCR 모델 로딩을 워커 진입 전에 미리 (UI 끊기지 않게)"""
            try:
                from core.kakao_friends import _get_paddle_ocr
                _get_paddle_ocr()
            except Exception as e:
                # 사전 초기화 실패도 무방 — 워커가 폴백 OCR 사용
                print(f"[SyncDialog] paddle pre-init: {e}")
            self.after(0, self._start_worker)

        threading.Thread(target=preinit, daemon=True).start()

    def _start_worker(self):
        """OCR 엔진 준비 완료 → 실제 동기화 시작"""
        import threading

        self.status_label.configure(text="실행 중... (카톡 친구탭 자동조작)")
        self.update_idletasks()

        def runner():
            import traceback
            try:
                self._result = self.orchestrator.run_kakao_friends_sync(
                    category="kakao_friend",
                    dry_run=False,
                    max_count=2000,
                    on_progress=self._progress_cb,
                    should_stop=lambda: self._stop_flag,
                )
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[SyncDialog 워커 예외]\n{tb}")
                self._result = {
                    "ok": False,
                    "reason": f"{type(e).__name__}: {e}",
                    "traceback": tb,
                    "added": 0, "duplicates": 0, "ocr_failed": 0,
                }
            finally:
                self.after(0, self._on_finished)

        self._thread = threading.Thread(target=runner, daemon=True)
        self._thread.start()

    def _progress_cb(self, target, action, idx):
        name = target.get("name", "?") if isinstance(target, dict) else str(target)
        self.after(0, lambda: self._on_step(name, action, idx))

    def _on_step(self, name: str, action: str, idx: int):
        if action == "added":
            self._added += 1
            self._append_to_list(f"  + {self._added:3d}. {name}")
            if self._added % 5 == 0:
                parent = self.master
                if hasattr(parent, "refresh_list"):
                    parent.refresh_list(category="kakao_friend")
        elif action == "added_homonym":
            self._added += 1
            self._append_to_list(f"  ◆ {self._added:3d}. {name}  [동명이인]")
            if self._added % 5 == 0:
                parent = self.master
                if hasattr(parent, "refresh_list"):
                    parent.refresh_list(category="kakao_friend")
        elif action == "duplicate_existing":
            self._dup += 1
            self._append_to_list(f"  · {name} (이미 있음 - 스킵)")
        elif action == "duplicate":
            self._dup += 1
        elif action == "ocr_failed":
            self._fail += 1

        self.added_label.configure(text=f"✓ 추가: {self._added}")
        self.dup_label.configure(text=f"· 중복: {self._dup}")
        self.fail_label.configure(text=f"× OCR실패: {self._fail}")

    def _append_to_list(self, line: str):
        self.list_box.configure(state="normal")
        self.list_box.insert("end", line + "\n")
        self.list_box.see("end")
        self.list_box.configure(state="disabled")

    def _on_stop(self):
        self._stop_flag = True
        self.stop_btn.configure(state="disabled", text="중단 중...")
        self.status_label.configure(text="중단 처리 중... (지금까지 추가된 건 그대로 유지)")

    def _on_finished(self):
        self.stop_btn.configure(state="disabled")
        self.close_btn.configure(state="normal")

        if not self._result:
            self.status_label.configure(text="알 수 없는 오류")
            return

        r = self._result
        if r.get("ok"):
            reason = r.get("reason") or "완료"
            self.status_label.configure(text=f"✅ {reason}")
        else:
            self.status_label.configure(
                text=f"❌ 실패 — {r.get('reason', '')}",
                text_color="#c0392b",
            )

        if self.on_done:
            self.on_done(r)

    def _on_close(self):
        """닫기 버튼 — 항상 즉시 destroy (워커 끝난 후라 안전)"""
        self.destroy()

    def _on_window_close(self):
        """X 버튼.
        - 워커 실행 중이면 1번만 stop 신호 → 1.5초 후 강제 destroy.
        - 워커는 daemon 이라 메인 종료 시 자동 회수, 강제 닫아도 안전.
        """
        if self._thread and self._thread.is_alive() and not self._stop_flag:
            self._stop_flag = True
            self.status_label.configure(text="중단 신호 전송 — 1.5초 후 닫힘")
            self.after(1500, self._force_destroy)
            return
        # 이미 중단 시도했거나 워커 종료됨 → 즉시 닫기
        self.destroy()

    def _force_destroy(self):
        """강제 닫기 — 워커가 응답 안 해도 닫힘 (daemon 스레드 자동 회수)"""
        try:
            self.destroy()
        except Exception:
            pass
