"""
Settings Page - 설정 페이지
위치 학습 마법사 + 안전 장치 + 미니맵 + 스크린샷 검증
"""

import json
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from pathlib import Path
from ui.theme import AppTheme as T

try:
    import pyautogui
except ImportError:
    pyautogui = None


# ──────────────────────────────────────────────────────────
#  투명 오버레이 - 클릭 위치 캡처
# ──────────────────────────────────────────────────────────

class ClickCaptureOverlay(ctk.CTkToplevel):
    """거의 투명한 전체화면 오버레이. 클릭하면 해당 좌표를 기록하고 닫힘."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.click_pos = None

        # 전체화면 + 거의 투명 + 최상위
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.01)
        except Exception:
            pass

        # 화면 전체 덮기
        if pyautogui:
            sw, sh = pyautogui.size()
        else:
            sw, sh = 1920, 1080
        self.geometry(f"{sw}x{sh}+0+0")

        # 클릭 이벤트
        self.bind("<Button-1>", self._on_click)

    def _on_click(self, event):
        self.click_pos = (event.x_root, event.y_root)
        self.destroy()


# ──────────────────────────────────────────────────────────
#  위치 학습 마법사 (실제 카톡 워크플로우 순서)
# ──────────────────────────────────────────────────────────

LEARNING_STEPS = [
    {
        "key": "search_icon",
        "title": "Step 1/8: 돋보기(검색) 아이콘",
        "desc": "카카오톡 상단의 🔍 돋보기 아이콘을 클릭하세요.\n(검색 모드로 진입합니다)",
        "color": "#f85149",
        "action": "click",
    },
    {
        "key": "search_input",
        "title": "Step 2/8: 검색 입력창",
        "desc": "검색 입력 필드를 클릭하세요.\n(돋보기 클릭 후 나타나는 입력창)",
        "color": "#fae100",
        "action": "click",
    },
    {
        "key": "first_result",
        "title": "Step 3/8: 검색 결과 클릭",
        "desc": "아무 이름이나 검색 후,\n검색 결과에서 아무 사람을 클릭하세요.\n(채팅방이 열립니다)",
        "color": "#d29922",
        "action": "click",
    },
    {
        "key": "message_input",
        "title": "Step 4/8: 메시지 입력창",
        "desc": "채팅방 하단의 메시지 입력창을 클릭하세요.",
        "color": "#58a6ff",
        "action": "click",
    },
    {
        "key": "send_enter",
        "title": "Step 5/8: 보내기(전송) 버튼",
        "desc": "채팅방 하단의 전송 버튼을 클릭하세요.\n(메시지 입력창 오른쪽에 있는 전송 버튼)",
        "color": "#bc8cff",
        "action": "click",
    },
    {
        "key": "image_send",
        "title": "Step 6/8: 이미지 전송 버튼",
        "desc": "이미지를 붙여넣기(Cmd+V) 하면 나타나는\n전송 확인 팝업의 '전송' 버튼을 클릭하세요.\n\n※ 먼저 입력창에 이미지를 붙여넣기 해주세요.",
        "color": "#ff7b72",
        "action": "click",
    },
    {
        "key": "back_button",
        "title": "Step 7/8: 뒤로가기/닫기",
        "desc": "채팅방에서 나가는 버튼을 클릭하세요.\n(← 뒤로가기 또는 ESC)",
        "color": "#3fb950",
        "action": "click",
    },
    {
        "key": "friends_tab_icon",
        "title": "Step 8/8: 친구탭 사람 아이콘",
        "desc": "좌측 사이드바의 사람 아이콘(👤)을 클릭하세요.\n(채팅탭에서 친구탭으로 전환할 때 사용)\n\n※ 시작 상태 자동화의 핵심 좌표입니다.",
        "color": "#79c0ff",
        "action": "click",
    },
]


class PositionLearningWizard(ctk.CTkToplevel):
    """
    위치 학습 마법사
    실제 카카오톡 워크플로우 순서대로 각 UI 요소를 클릭하면
    그 좌표를 기록한다.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("위치 학습")
        self.geometry("380x460+50+100")
        self.configure(fg_color=T.BG_DARK)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self.result = {}
        self.current_step = 0
        self.completed = False
        self._overlay = None

        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="카카오톡 UI 위치 학습",
            font=(T.get_font_family(), 16, "bold"),
            text_color=T.ACCENT
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            self, text="각 단계에서 해당 요소를 직접 클릭하세요.",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_SECONDARY
        ).pack(pady=(0, 12))

        # 진행 바
        self.progress_bar = ctk.CTkProgressBar(
            self, height=6, progress_color=T.ACCENT, fg_color=T.BG_INPUT
        )
        self.progress_bar.pack(fill="x", padx=24, pady=(0, 12))
        self.progress_bar.set(0)

        # 단계 카드
        self.step_card = ctk.CTkFrame(
            self, fg_color=T.BG_CARD, corner_radius=10,
            border_width=2, border_color=T.BORDER
        )
        self.step_card.pack(fill="x", padx=24, pady=(0, 12))

        self.step_title = ctk.CTkLabel(
            self.step_card, text="",
            font=(T.get_font_family(), 14, "bold"),
            text_color=T.TEXT_PRIMARY
        )
        self.step_title.pack(padx=16, pady=(16, 6))

        self.step_desc = ctk.CTkLabel(
            self.step_card, text="",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_SECONDARY, justify="center", wraplength=320
        )
        self.step_desc.pack(padx=16, pady=(0, 8))

        self.recorded_label = ctk.CTkLabel(
            self.step_card, text="",
            font=(T.get_font_family(), 12, "bold"),
            text_color=T.SUCCESS
        )
        self.recorded_label.pack(padx=16, pady=(0, 12))

        # 마우스 실시간 좌표
        self.mouse_label = ctk.CTkLabel(
            self, text="마우스: (-, -)",
            font=(T.get_font_family(), 11),
            text_color=T.TEXT_MUTED
        )
        self.mouse_label.pack(pady=(0, 8))

        # 버튼들
        self.click_btn = ctk.CTkButton(
            self, text="클릭으로 위치 기록",
            font=(T.get_font_family(), 13, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, height=44, corner_radius=8,
            command=self._start_click_capture
        )
        self.click_btn.pack(fill="x", padx=24, pady=(0, 6))

        self.timer_btn = ctk.CTkButton(
            self, text="3초 후 자동 기록",
            font=(T.get_font_family(), 11),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=34, corner_radius=6,
            command=self._start_countdown
        )
        self.timer_btn.pack(fill="x", padx=24, pady=(0, 8))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkButton(
            bottom, text="취소", width=70,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=6,
            command=self._cancel
        ).pack(side="left")

        self.skip_btn = ctk.CTkButton(
            bottom, text="건너뛰기", width=80,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_MUTED, height=30, corner_radius=6,
            command=self._skip_step
        )
        self.skip_btn.pack(side="right")

        self._show_step()
        self._update_mouse_pos()

    def _show_step(self):
        if self.current_step >= len(LEARNING_STEPS):
            self._finish()
            return

        step = LEARNING_STEPS[self.current_step]
        self.step_card.configure(border_color=step["color"])
        self.step_title.configure(text=step["title"], text_color=step["color"])
        self.step_desc.configure(text=step["desc"])
        self.recorded_label.configure(text="")
        self.progress_bar.set(self.current_step / len(LEARNING_STEPS))

        if step["action"] == "confirm_only":
            self.click_btn.configure(text="확인 (Enter로 전송)", command=self._confirm_step)
            self.timer_btn.pack_forget()
        else:
            self.click_btn.configure(text="클릭으로 위치 기록", command=self._start_click_capture)
            self.timer_btn.pack(fill="x", padx=24, pady=(0, 8))

    def _update_mouse_pos(self):
        if pyautogui and self.winfo_exists():
            try:
                x, y = pyautogui.position()
                self.mouse_label.configure(text=f"마우스: ({x}, {y})")
            except Exception:
                pass
            self.after(100, self._update_mouse_pos)

    def _start_click_capture(self):
        """투명 오버레이를 띄워서 다음 클릭 위치를 캡처"""
        self.click_btn.configure(state="disabled", text="카카오톡에서 클릭하세요...")
        self.timer_btn.configure(state="disabled")

        # 오버레이 생성
        self._overlay = ClickCaptureOverlay(self)
        self._overlay.bind("<Destroy>", self._on_overlay_closed)

    def _on_overlay_closed(self, event=None):
        """오버레이가 닫히면 (클릭됨) 좌표 기록"""
        if self._overlay and self._overlay.click_pos:
            x, y = self._overlay.click_pos
            self._record_pos(x, y)
        else:
            # 클릭 없이 닫힘
            self.click_btn.configure(state="normal", text="클릭으로 위치 기록")
            self.timer_btn.configure(state="normal")
        self._overlay = None

    def _start_countdown(self):
        """3초 카운트다운"""
        self.click_btn.configure(state="disabled")
        self.timer_btn.configure(state="disabled", text="3...")
        self.after(1000, lambda: self.timer_btn.configure(text="2..."))
        self.after(2000, lambda: self.timer_btn.configure(text="1..."))
        self.after(3000, self._record_from_mouse)

    def _record_from_mouse(self):
        """현재 마우스 위치 기록"""
        if pyautogui:
            x, y = pyautogui.position()
            self._record_pos(x, y)

    def _record_pos(self, x, y):
        """좌표 기록 후 다음 단계 준비"""
        step = LEARNING_STEPS[self.current_step]
        self.result[step["key"]] = {"x": x, "y": y, "description": step["title"]}

        self.recorded_label.configure(text=f"기록: ({x}, {y})")

        self.click_btn.configure(
            state="normal", text="다음 →",
            command=self._next_step
        )
        self.timer_btn.configure(state="normal", text="3초 후 자동 기록")

    def _confirm_step(self):
        """확인만 하는 단계 (보내기 등)"""
        step = LEARNING_STEPS[self.current_step]
        # message_input 좌표를 send_enter에도 재사용
        msg_pos = self.result.get("message_input", {})
        if msg_pos:
            self.result[step["key"]] = {
                "x": msg_pos["x"], "y": msg_pos["y"],
                "description": step["title"]
            }
        self.recorded_label.configure(text="확인됨")
        self._next_step()

    def _next_step(self):
        self.current_step += 1
        self._show_step()

    def _skip_step(self):
        self.current_step += 1
        self._show_step()

    def _finish(self):
        self.progress_bar.set(1.0)
        self.step_title.configure(text="학습 완료!", text_color=T.SUCCESS)
        self.step_card.configure(border_color=T.SUCCESS)

        lines = []
        for step in LEARNING_STEPS:
            pos = self.result.get(step["key"])
            if pos:
                lines.append(f"{step['key']}: ({pos['x']}, {pos['y']})")
            else:
                lines.append(f"{step['key']}: (건너뜀)")
        self.step_desc.configure(text="\n".join(lines), justify="left")
        self.recorded_label.configure(text="")

        self.click_btn.configure(
            text="셋팅 완료 - 저장",
            state="normal",
            fg_color=T.SUCCESS, hover_color="#2ea043",
            command=self._save_and_close
        )
        self.timer_btn.pack_forget()
        self.skip_btn.pack_forget()

    def _save_and_close(self):
        self.completed = True
        self.destroy()

    def _cancel(self):
        self.completed = False
        if self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
        self.destroy()


# ──────────────────────────────────────────────────────────
#  미니맵 위젯 - 모니터 + 카카오톡 위치 시각화
# ──────────────────────────────────────────────────────────

class MinimapCanvas(ctk.CTkFrame):
    """모니터 위에 카카오톡 창 위치를 보여주는 미니맵"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=T.BG_CARD, corner_radius=10,
                         border_width=1, border_color=T.BORDER, **kwargs)
        self.canvas_w = 300
        self.canvas_h = 180

        ctk.CTkLabel(
            self, text="🖥 카카오톡 창 위치",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(padx=12, pady=(12, 4), anchor="w")

        self.canvas = tk.Canvas(
            self, width=self.canvas_w, height=self.canvas_h,
            bg="#1a1b26", highlightthickness=0, bd=0
        )
        self.canvas.pack(padx=12, pady=(0, 12))

        self.info_label = ctk.CTkLabel(
            self, text="", font=(T.get_font_family(), 9),
            text_color=T.TEXT_MUTED
        )
        self.info_label.pack(padx=12, pady=(0, 8))

    def draw(self, screen_w, screen_h, kakao_rect):
        """미니맵 그리기"""
        self.canvas.delete("all")

        if not screen_w or not screen_h:
            return

        # 스케일 계산
        pad = 10
        usable_w = self.canvas_w - pad * 2
        usable_h = self.canvas_h - pad * 2
        scale = min(usable_w / screen_w, usable_h / screen_h)

        # 모니터 영역
        mw = int(screen_w * scale)
        mh = int(screen_h * scale)
        mx = (self.canvas_w - mw) // 2
        my = (self.canvas_h - mh) // 2

        self.canvas.create_rectangle(
            mx, my, mx + mw, my + mh,
            outline="#3d59a1", width=2, fill="#16161e"
        )
        self.canvas.create_text(
            mx + mw // 2, my + mh // 2,
            text=f"{screen_w}×{screen_h}", fill="#565f89",
            font=("Helvetica", 9)
        )

        # 카카오톡 창
        if kakao_rect:
            kx = mx + int(kakao_rect.get("x", 0) * scale)
            ky = my + int(kakao_rect.get("y", 0) * scale)
            kw = int(kakao_rect.get("width", 420) * scale)
            kh = int(kakao_rect.get("height", 700) * scale)

            self.canvas.create_rectangle(
                kx, ky, kx + kw, ky + kh,
                outline="#fae100", width=2, fill="#2d2a1e"
            )
            self.canvas.create_text(
                kx + kw // 2, ky + kh // 2,
                text="카톡", fill="#fae100", font=("Helvetica", 8, "bold")
            )

            self.info_label.configure(
                text=f"카카오톡: ({kakao_rect['x']}, {kakao_rect['y']}) "
                     f"{kakao_rect['width']}×{kakao_rect['height']}"
            )


# ──────────────────────────────────────────────────────────
#  스크린샷 검증 다이얼로그 (좌표 마커 인라인 표시)
# ──────────────────────────────────────────────────────────

class VerifyScreenshotDialog(ctk.CTkToplevel):
    """스크린샷 위에 좌표 마커를 표시하는 검증 다이얼로그"""

    def __init__(self, parent, image_path, positions, kakao_rect, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("좌표 검증 - 스크린샷")
        self.configure(fg_color=T.BG_DARK)
        self.attributes("-topmost", True)

        try:
            from PIL import Image, ImageTk, ImageDraw, ImageFont

            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            kx = kakao_rect.get("x", 0)
            ky = kakao_rect.get("y", 0)

            step_colors = {s["key"]: s["color"] for s in LEARNING_STEPS}
            step_names = {s["key"]: s["title"].split(":")[1].strip() if ":" in s["title"] else s["key"]
                          for s in LEARNING_STEPS}

            for key, coord in positions.items():
                if not isinstance(coord, dict) or "x" not in coord:
                    continue
                color_hex = step_colors.get(key, "#ffffff")
                r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
                rx = coord["x"] - kx
                ry = coord["y"] - ky
                # 원 + 십자
                draw.ellipse([rx - 14, ry - 14, rx + 14, ry + 14],
                             outline=(r, g, b), width=3)
                draw.line([rx - 20, ry, rx + 20, ry], fill=(r, g, b), width=2)
                draw.line([rx, ry - 20, rx, ry + 20], fill=(r, g, b), width=2)
                # 라벨
                label = step_names.get(key, key)
                draw.text((rx + 18, ry - 8), label, fill=(r, g, b))

            # 이미지 표시 크기 (최대 600px 너비)
            max_w = 600
            ratio = min(max_w / img.width, 1.0)
            display_w = int(img.width * ratio)
            display_h = int(img.height * ratio)
            img_resized = img.resize((display_w, display_h), Image.LANCZOS)

            self.geometry(f"{display_w + 40}x{display_h + 120}")

            ctk.CTkLabel(
                self, text="학습된 좌표가 올바른 위치에 있는지 확인하세요",
                font=(T.get_font_family(), 12, "bold"),
                text_color=T.TEXT_PRIMARY
            ).pack(pady=(12, 8))

            # Canvas에 이미지 표시
            self._photo = ImageTk.PhotoImage(img_resized)
            canvas = tk.Canvas(
                self, width=display_w, height=display_h,
                bg="#1a1b26", highlightthickness=1, highlightbackground=T.BORDER
            )
            canvas.pack(padx=20, pady=(0, 8))
            canvas.create_image(0, 0, anchor="nw", image=self._photo)

            # 범례
            legend_frame = ctk.CTkFrame(self, fg_color="transparent")
            legend_frame.pack(fill="x", padx=20, pady=(0, 4))
            for step in LEARNING_STEPS:
                pos = positions.get(step["key"])
                if not pos or not isinstance(pos, dict) or "x" not in pos:
                    continue
                name = step["title"].split(":")[1].strip() if ":" in step["title"] else step["key"]
                ctk.CTkLabel(
                    legend_frame,
                    text=f"● {name} ({pos['x']},{pos['y']})",
                    font=(T.get_font_family(), 9),
                    text_color=step["color"]
                ).pack(side="left", padx=(0, 12))

            ctk.CTkButton(
                self, text="확인", width=100, height=32,
                font=(T.get_font_family(), T.FONT_SIZE_BODY),
                fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                text_color=T.TEXT_ON_ACCENT, corner_radius=6,
                command=self.destroy
            ).pack(pady=(4, 12))

        except Exception as e:
            ctk.CTkLabel(
                self, text=f"스크린샷 표시 실패: {e}",
                font=(T.get_font_family(), 12),
                text_color=T.ERROR, wraplength=500
            ).pack(padx=20, pady=20)
            self.geometry("550x100")


# ──────────────────────────────────────────────────────────
#  설정 페이지
# ──────────────────────────────────────────────────────────

class SettingsPage(ctk.CTkFrame):
    """설정 페이지"""

    def __init__(self, parent, orchestrator=None, **kwargs):
        super().__init__(parent, fg_color=T.BG_DARK, **kwargs)
        self.orchestrator = orchestrator
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        header.pack(fill="x", padx=24, pady=(20, 16))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="⚙️ 설정",
            font=(T.get_font_family(), T.FONT_SIZE_TITLE, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=T.BG_HOVER
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # ── 위치 학습 ──
        learn_card = self._create_card(scroll, "🎯 카카오톡 UI 위치 학습 (필수)")

        ctk.CTkLabel(
            learn_card,
            text=(
                "실제 카카오톡에서 각 버튼을 직접 클릭하여 위치를 기록합니다.\n"
                "순서: 돋보기 → 검색창 → 결과 클릭 → 메시지 입력 → 보내기 → 닫기\n"
                "한 번 학습하면 저장되어 계속 사용됩니다."
            ),
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, wraplength=500, justify="left"
        ).pack(padx=16, pady=(0, 8), anchor="w")

        # 학습 상태
        self.learn_status_frame = ctk.CTkFrame(
            learn_card, fg_color=T.BG_INPUT, corner_radius=6
        )
        self.learn_status_frame.pack(fill="x", padx=16, pady=(0, 8))

        self.learn_status_label = ctk.CTkLabel(
            self.learn_status_frame, text="",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED, justify="left"
        )
        self.learn_status_label.pack(padx=12, pady=8, anchor="w")
        self._update_learn_status()

        # 버튼
        learn_btn_frame = ctk.CTkFrame(learn_card, fg_color="transparent")
        learn_btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkButton(
            learn_btn_frame, text="위치 학습 시작",
            font=(T.get_font_family(), 14, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, height=44, corner_radius=8,
            command=self._start_learning
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            learn_btn_frame, text="스크린샷 검증",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6,
            command=self._verify_screenshot
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            learn_btn_frame, text="초기화",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_HOVER, hover_color=T.ERROR,
            text_color=T.TEXT_MUTED, height=30, corner_radius=6,
            command=self._reset_positions
        ).pack(side="right")

        # ── 미니맵 (카카오톡 창 위치 시각화) + 자동 배치 버튼 ──
        minimap_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        minimap_frame.pack(fill="x", pady=(0, 12))

        self.minimap = MinimapCanvas(minimap_frame)
        self.minimap.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            minimap_frame, text="📐 카카오톡\n자동 배치",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            fg_color="#1a5276", hover_color="#2471a3",
            text_color=T.TEXT_PRIMARY, width=120, height=60, corner_radius=8,
            command=self._position_kakao
        ).pack(side="left", padx=(0, 8), anchor="center")

        self._refresh_minimap()

        # ── 안전 장치 안내 ──
        safety_card = self._create_card(scroll, "🛡 안전 장치")

        ctk.CTkLabel(
            safety_card,
            text=(
                "• 발송 중 에러 발생 → 즉시 정지 + 알림\n"
                "• 마우스를 화면 좌측 상단 모서리로 이동 → 긴급 정지\n"
                "• OCR 검증: 검색 후 결과 클릭 전에 이름 확인\n"
                "• 검증 실패 시 해당 건 건너뛰고 다음 진행"
            ),
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, wraplength=500, justify="left"
        ).pack(padx=16, pady=(0, 16), anchor="w")

        # ── 카카오톡 창 배치 ──
        kakao_card = self._create_card(scroll, "💬 카카오톡 창 배치")

        self.kakao_width = self._create_setting_row(kakao_card, "창 너비 (px)", "420")
        self.kakao_height = self._create_setting_row(kakao_card, "창 높이 (px)", "700")
        self.kakao_margin_r = self._create_setting_row(kakao_card, "우측 여백 (px)", "20")
        self.kakao_margin_t = self._create_setting_row(kakao_card, "상단 여백 (px)", "40")

        kakao_btn_frame = ctk.CTkFrame(kakao_card, fg_color="transparent")
        kakao_btn_frame.pack(fill="x", padx=16, pady=(8, 16))

        ctk.CTkButton(
            kakao_btn_frame, text="📐 카카오톡 자동 배치",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_HOVER, hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6,
            command=self._position_kakao
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            kakao_btn_frame, text="💾 카카오톡 위치 저장",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color="#2ea043", hover_color="#3fb950",
            text_color=T.TEXT_PRIMARY, height=36, corner_radius=6,
            command=self._save_kakao_position
        ).pack(side="left")

        # ── 발송 설정 ──
        send_card = self._create_card(scroll, "🚀 발송 설정")

        self.delay_min = self._create_setting_row(send_card, "최소 딜레이 (초)", "30")
        self.delay_max = self._create_setting_row(send_card, "최대 딜레이 (초)", "120")
        self.retry_count = self._create_setting_row(send_card, "재시도 횟수", "2")

        # ── 계정 보호 ──
        protect_card = self._create_card(scroll, "🛡 계정 보호 (자동 감지 방지)")

        ctk.CTkLabel(
            protect_card,
            text=(
                "봇 탐지를 피하기 위해 사람처럼 행동합니다.\n"
                "마우스 곡선 이동 + 랜덤 딜레이 + 주기적 휴식"
            ),
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, wraplength=500, justify="left"
        ).pack(padx=16, pady=(0, 8), anchor="w")

        self.action_delay_min = self._create_setting_row(protect_card, "동작 간 최소 딜레이 (초)", "0.3")
        self.action_delay_max = self._create_setting_row(protect_card, "동작 간 최대 딜레이 (초)", "1.0")
        self.rest_every = self._create_setting_row(protect_card, "N명마다 휴식", "15")
        self.rest_min_s = self._create_setting_row(protect_card, "휴식 최소 (초)", "180")
        self.rest_max_s = self._create_setting_row(protect_card, "휴식 최대 (초)", "420")
        self.daily_limit_entry = self._create_setting_row(protect_card, "일일 최대 발송 (0=무제한)", "150")

        # ── OCR 설정 ──
        ocr_card = self._create_card(scroll, "👁 OCR 설정")

        self.ocr_lang = self._create_setting_row(ocr_card, "언어", "kor+eng")
        self.ocr_confidence = self._create_setting_row(ocr_card, "최소 신뢰도 (%)", "70")

        # ── 생일/기념일 자동 발송 ──
        auto_card = self._create_card(scroll, "🎂 생일/기념일 자동 발송")

        ctk.CTkLabel(
            auto_card,
            text=(
                "연락처에 생일/기념일이 등록되어 있으면\n"
                "해당 날짜에 자동으로 메시지를 발송합니다."
            ),
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, wraplength=500, justify="left"
        ).pack(padx=16, pady=(0, 8), anchor="w")

        # 활성화 토글
        auto_toggle_frame = ctk.CTkFrame(auto_card, fg_color="transparent", height=36)
        auto_toggle_frame.pack(fill="x", padx=16, pady=4)
        auto_toggle_frame.pack_propagate(False)
        ctk.CTkLabel(
            auto_toggle_frame, text="자동 발송 활성화",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        self.auto_send_var = ctk.BooleanVar(value=False)
        self.auto_send_switch = ctk.CTkSwitch(
            auto_toggle_frame, text="",
            variable=self.auto_send_var,
            onvalue=True, offvalue=False,
            progress_color=T.ACCENT,
            command=self._update_auto_send_warning,
        )
        self.auto_send_switch.pack(side="left")

        # 미설정 경고 라벨 (조건부 표시)
        self.auto_warn_label = ctk.CTkLabel(
            auto_toggle_frame, text="",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL, "bold"),
            text_color=T.ERROR,
        )
        self.auto_warn_label.pack(side="left", padx=(12, 0))

        # 발송 모드 (json: contacts.json birthday 필드 / kakao_ocr: 카톡 친구탭 OCR)
        mode_frame = ctk.CTkFrame(auto_card, fg_color="transparent", height=36)
        mode_frame.pack(fill="x", padx=16, pady=4)
        mode_frame.pack_propagate(False)
        ctk.CTkLabel(
            mode_frame, text="발송 모드",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        self.auto_mode_var = ctk.StringVar(value="저장된 연락처")
        self.auto_mode_menu = ctk.CTkOptionMenu(
            mode_frame,
            values=["저장된 연락처", "카톡 친구탭 자동인식"],
            variable=self.auto_mode_var,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=4,
            width=200,
        )
        self.auto_mode_menu.pack(side="left")

        ctk.CTkLabel(
            auto_card,
            text="• 저장된 연락처: 입력된 생일(MM-DD) 기반\n"
                 "• 카톡 친구탭 자동인식: 카톡 PC 띄워둬야 함, OCR 로 오늘 생일자 식별",
            font=(T.get_font_family(), 10),
            text_color=T.TEXT_TERTIARY if hasattr(T, 'TEXT_TERTIARY') else T.TEXT_SECONDARY,
            justify="left"
        ).pack(padx=16, pady=(0, 4), anchor="w")

        # ── 연락처 DB 자동 반영 옵션 ──
        sync_frame = ctk.CTkFrame(auto_card, fg_color="transparent", height=36)
        sync_frame.pack(fill="x", padx=16, pady=4)
        sync_frame.pack_propagate(False)
        ctk.CTkLabel(
            sync_frame, text="발견 생일자 DB 자동 반영",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        self.sync_bd_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            sync_frame, text="동명 연락처 빈 생일 채움",
            variable=self.sync_bd_var,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            progress_color=T.SUCCESS,
        ).pack(side="left")

        create_frame = ctk.CTkFrame(auto_card, fg_color="transparent", height=36)
        create_frame.pack(fill="x", padx=16, pady=4)
        create_frame.pack_propagate(False)
        ctk.CTkLabel(
            create_frame, text="",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        self.sync_create_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            create_frame, text="미매칭이면 새 연락처 생성",
            variable=self.sync_create_var,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            progress_color=T.WARNING if hasattr(T, "WARNING") else T.ACCENT,
        ).pack(side="left")

        # 발송 시간
        auto_time_frame = ctk.CTkFrame(auto_card, fg_color="transparent", height=36)
        auto_time_frame.pack(fill="x", padx=16, pady=4)
        auto_time_frame.pack_propagate(False)
        ctk.CTkLabel(
            auto_time_frame, text="발송 시간",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        self.auto_hour = ctk.CTkEntry(
            auto_time_frame, width=50, height=30,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=4
        )
        self.auto_hour.pack(side="left")
        self.auto_hour.insert(0, "9")
        ctk.CTkLabel(
            auto_time_frame, text="시",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(4, 8))
        self.auto_minute = ctk.CTkEntry(
            auto_time_frame, width=50, height=30,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=4
        )
        self.auto_minute.pack(side="left")
        self.auto_minute.insert(0, "0")
        ctk.CTkLabel(
            auto_time_frame, text="분",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY
        ).pack(side="left", padx=(4, 0))

        # 생일 템플릿 선택
        bd_tmpl_frame = ctk.CTkFrame(auto_card, fg_color="transparent", height=36)
        bd_tmpl_frame.pack(fill="x", padx=16, pady=4)
        bd_tmpl_frame.pack_propagate(False)
        ctk.CTkLabel(
            bd_tmpl_frame, text="생일 메시지 템플릿",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        self.bd_template_var = ctk.StringVar(value="(없음)")
        self.bd_template_menu = ctk.CTkOptionMenu(
            bd_tmpl_frame, values=["(없음)"],
            variable=self.bd_template_var,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=4,
            width=200,
            command=lambda _: self._update_auto_send_warning(),
        )
        self.bd_template_menu.pack(side="left")

        # 기념일 템플릿 선택
        an_tmpl_frame = ctk.CTkFrame(auto_card, fg_color="transparent", height=36)
        an_tmpl_frame.pack(fill="x", padx=16, pady=4)
        an_tmpl_frame.pack_propagate(False)
        ctk.CTkLabel(
            an_tmpl_frame, text="기념일 메시지 템플릿",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        self.an_template_var = ctk.StringVar(value="(없음)")
        self.an_template_menu = ctk.CTkOptionMenu(
            an_tmpl_frame, values=["(없음)"],
            variable=self.an_template_var,
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            fg_color=T.BG_INPUT, button_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, height=30, corner_radius=4,
            width=200
        )
        self.an_template_menu.pack(side="left")

        # 템플릿 드롭다운 로드
        self._refresh_auto_send_templates()
        self._update_auto_send_warning()

        # 하단 여백
        ctk.CTkFrame(auto_card, fg_color="transparent", height=12).pack()

        # ── 세종텔레콤 (알림톡/SMS) 설정 ──
        sejong_card = self._create_card(scroll, "📡 세종텔레콤 (알림톡/SMS)")

        ctk.CTkLabel(
            sejong_card,
            text="알림톡, SMS/LMS 공식 발송을 위한 DB 연결 설정입니다.",
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, wraplength=500, justify="left"
        ).pack(padx=16, pady=(0, 8), anchor="w")

        # DB 연결
        db_label = ctk.CTkLabel(
            sejong_card, text="  DB 연결",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.INFO
        )
        db_label.pack(padx=16, pady=(4, 4), anchor="w")

        self.sj_db_host = self._create_setting_row(sejong_card, "DB 호스트", "localhost")
        self.sj_db_port = self._create_setting_row(sejong_card, "DB 포트", "3306")
        self.sj_db_name = self._create_setting_row(sejong_card, "DB 이름", "sms")
        self.sj_db_user = self._create_setting_row(sejong_card, "DB 사용자", "")
        self.sj_db_password = self._create_setting_row(sejong_card, "DB 비밀번호", "")
        # 비밀번호 마스킹
        self.sj_db_password.configure(show="●")

        # 카카오 설정
        kakao_label = ctk.CTkLabel(
            sejong_card, text="  카카오 알림톡",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            text_color=T.INFO
        )
        kakao_label.pack(padx=16, pady=(12, 4), anchor="w")

        self.sj_sender_key = self._create_setting_row(sejong_card, "발신프로필 키 (sender_key)", "")
        self.sj_callback = self._create_setting_row(sejong_card, "발신번호 (callback)", "")
        self.sj_template_code = self._create_setting_row(sejong_card, "템플릿 코드", "")

        # 연결 테스트 버튼
        sj_btn_frame = ctk.CTkFrame(sejong_card, fg_color="transparent", height=40)
        sj_btn_frame.pack(fill="x", padx=16, pady=(8, 12))
        sj_btn_frame.pack_propagate(False)

        ctk.CTkButton(
            sj_btn_frame, text="🔌 DB 연결 테스트", width=160, height=32,
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            fg_color="#2471a3", hover_color="#3498db",
            text_color="#ffffff", corner_radius=6,
            command=self._test_sejong_connection
        ).pack(side="left", padx=(0, 8))

        self.sj_status_label = ctk.CTkLabel(
            sj_btn_frame, text="미연결",
            font=(T.get_font_family(), T.FONT_SIZE_SMALL),
            text_color=T.TEXT_MUTED
        )
        self.sj_status_label.pack(side="left")

        # ── 시스템 정보 ──
        info_card = self._create_card(scroll, "🖥 시스템 정보")

        if self.orchestrator:
            screen = self.orchestrator.window_ctrl.get_screen_info()
            self._create_info_row(info_card, "운영체제", screen["system"])
            self._create_info_row(info_card, "해상도",
                                  f"{screen['screen_width']}x{screen['screen_height']}")
            self._create_info_row(info_card, "DPI 스케일", f"{screen['dpi_scale']}x")

        # ── 저장 ──
        ctk.CTkButton(
            scroll, text="💾 설정 저장",
            font=(T.get_font_family(), T.FONT_SIZE_BODY, "bold"),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_ON_ACCENT, height=44, corner_radius=8,
            command=self._save_settings
        ).pack(pady=16)

        self._load_settings()

    # ── 미니맵 ──

    def _refresh_minimap(self):
        """미니맵 새로고침"""
        if not self.orchestrator:
            return
        screen = self.orchestrator.window_ctrl.get_screen_info()
        sw = screen["screen_width"]
        sh = screen["screen_height"]

        # 카카오톡 위치 계산
        self.orchestrator.window_ctrl.calculate_kakao_position()
        kakao_rect = self.orchestrator.window_ctrl.kakao_rect
        self.minimap.draw(sw, sh, kakao_rect)

    # ── 위치 학습 ──

    def _start_learning(self):
        if self.orchestrator:
            if not self.orchestrator.window_ctrl.find_kakao_window():
                messagebox.showerror("오류", "카카오톡이 실행 중이 아닙니다.\n먼저 카카오톡 PC를 실행해주세요.")
                return
            self.orchestrator.window_ctrl.activate_kakao()

        wizard = PositionLearningWizard(self.winfo_toplevel())
        self.wait_window(wizard)

        if wizard.completed and wizard.result:
            self._save_learned_positions(wizard.result)
            self._update_learn_status()

            if self.orchestrator:
                # 머지된 파일에서 다시 읽어 기존 키 (friends_tab_icon 등) 포함
                self.orchestrator.coordinates = self._load_learned_positions()
                self.orchestrator.confirm_calibration()

            messagebox.showinfo("학습 완료", f"{len(wizard.result)}개 위치 저장.\n발송 준비 완료!")

    def _verify_screenshot(self):
        if not self.orchestrator:
            return
        positions = self._load_learned_positions()
        if not positions:
            # 학습 파일 없으면 디폴트 좌표 사용
            positions = self.orchestrator.window_ctrl.calculate_ui_coordinates()
            if not positions:
                messagebox.showwarning("없음", "카카오톡을 먼저 실행하세요.")
                return

        if not self.orchestrator.window_ctrl.find_kakao_window():
            messagebox.showerror("오류", "카카오톡이 실행 중이 아닙니다.")
            return

        self.orchestrator.window_ctrl.activate_kakao()
        import time
        time.sleep(0.5)
        self.orchestrator.window_ctrl.calculate_kakao_position()
        kakao_rect = self.orchestrator.window_ctrl.kakao_rect

        try:
            screenshot = self.orchestrator.screen_capture.capture_kakao_window(kakao_rect)
            ss_path = self.orchestrator.screen_capture.save_screenshot(screenshot, "verify")

            # 인라인 다이얼로그로 스크린샷 + 좌표 마커 표시
            VerifyScreenshotDialog(
                self.winfo_toplevel(), ss_path, positions, kakao_rect
            )
        except Exception as e:
            messagebox.showerror("오류", f"스크린샷 캡처 실패:\n{e}")

    def _save_learned_positions(self, positions: dict):
        if not self.orchestrator:
            return
        path = self.orchestrator.base_dir / "config" / "learned_positions.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        # 기존 파일 키 보존 머지 — 마법사가 건너뛴 좌표/wizard 외부에서 추가된
        # 좌표 (예: friends_tab_icon 이 wizard 에 없던 시절) 가 덮어쓰기로
        # 소실되지 않도록 보호.
        merged = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    merged = json.load(f) or {}
            except Exception:
                merged = {}
        # 새로 학습한 좌표만 덮어쓰기 (값이 비어 있으면 기존 값 유지)
        for k, v in positions.items():
            if isinstance(v, dict) and "x" in v and "y" in v:
                merged[k] = v
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

    def _load_learned_positions(self) -> dict:
        if not self.orchestrator:
            return {}
        path = self.orchestrator.base_dir / "config" / "learned_positions.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _reset_positions(self):
        if messagebox.askyesno("초기화", "저장된 위치를 삭제하시겠습니까?"):
            if self.orchestrator:
                path = self.orchestrator.base_dir / "config" / "learned_positions.json"
                if path.exists():
                    path.unlink()
                self.orchestrator.coordinates = {}
                self.orchestrator.sender = None
            self._update_learn_status()

    def _update_learn_status(self):
        positions = self._load_learned_positions()
        if not positions:
            self.learn_status_label.configure(
                text="상태: 미학습 → '위치 학습 시작' 필요",
                text_color=T.ERROR
            )
            self.learn_status_frame.configure(border_width=1, border_color=T.ERROR)
            return

        lines = ["상태: 학습 완료"]
        for step in LEARNING_STEPS:
            pos = positions.get(step["key"])
            name = step["title"].split(":")[1].strip() if ":" in step["title"] else step["key"]
            if pos and isinstance(pos, dict) and "x" in pos:
                lines.append(f"  {name}: ({pos['x']}, {pos['y']})")
            else:
                lines.append(f"  {name}: (미설정)")

        self.learn_status_label.configure(text="\n".join(lines), text_color=T.SUCCESS)
        self.learn_status_frame.configure(border_width=1, border_color=T.SUCCESS)

    def _position_kakao(self):
        if not self.orchestrator:
            return
        if not self.orchestrator.window_ctrl.find_kakao_window():
            messagebox.showerror("오류", "카카오톡이 실행 중이 아닙니다.")
            return
        self.orchestrator.window_ctrl.activate_kakao()
        self.orchestrator.window_ctrl.calculate_kakao_position()
        ok = self.orchestrator.window_ctrl.position_kakao_window()
        self._refresh_minimap()
        if ok:
            messagebox.showinfo("완료", "카카오톡 창 배치 완료.")
        else:
            messagebox.showwarning("실패", "수동으로 배치해주세요.")

    def _save_kakao_position(self):
        if not self.orchestrator:
            return
        if not self.orchestrator.window_ctrl.find_kakao_window():
            messagebox.showerror("오류", "카카오톡이 실행 중이 아닙니다.\n원하는 위치에 배치 후 저장하세요.")
            return
        saved = self.orchestrator.window_ctrl.save_current_kakao_position()
        if saved:
            rect = self.orchestrator.window_ctrl.kakao_rect
            messagebox.showinfo("위치 저장 완료",
                f"카카오톡 창 위치가 저장되었습니다.\n\n"
                f"위치: ({rect['x']}, {rect['y']})\n"
                f"크기: {rect['width']}x{rect['height']}\n\n"
                f"다음부터 이 위치로 자동 배치됩니다.")
        else:
            messagebox.showwarning("실패", "카카오톡 위치 저장에 실패했습니다.")

    # ── 공통 UI ──

    def _create_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=T.BG_CARD,
                             corner_radius=T.CARD_RADIUS,
                             border_width=1, border_color=T.BORDER)
        card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            card, text=title,
            font=(T.get_font_family(), T.FONT_SIZE_HEADER, "bold"),
            text_color=T.TEXT_PRIMARY
        ).pack(padx=16, pady=(16, 8), anchor="w")
        return card

    def _create_setting_row(self, parent, label, default=""):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=36)
        row.pack(fill="x", padx=16, pady=4)
        row.pack_propagate(False)
        ctk.CTkLabel(
            row, text=label,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        entry = ctk.CTkEntry(
            row, width=120, height=30,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            fg_color=T.BG_INPUT, border_color=T.BORDER,
            text_color=T.TEXT_PRIMARY, corner_radius=4
        )
        entry.pack(side="left")
        entry.insert(0, default)
        return entry

    def _create_info_row(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        row.pack(fill="x", padx=16, pady=2)
        row.pack_propagate(False)
        ctk.CTkLabel(
            row, text=label,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_SECONDARY, width=180
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=value,
            font=(T.get_font_family(), T.FONT_SIZE_BODY),
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

    # ── 자동 발송 ──

    def _refresh_auto_send_templates(self):
        """템플릿 드롭다운 업데이트"""
        templates = []
        self._template_id_map = {}  # name → id
        if self.orchestrator:
            for t in self.orchestrator.message_engine.get_templates():
                templates.append(t.name)
                self._template_id_map[t.name] = t.id

        values = ["(없음)"] + templates
        self.bd_template_menu.configure(values=values)
        self.an_template_menu.configure(values=values)

    def _load_auto_send_settings(self):
        """스케줄러에서 자동 발송 설정 로드"""
        if not self.orchestrator:
            return
        settings = self.orchestrator.scheduler.auto_send_settings
        self.auto_send_var.set(settings.get("enabled", False))
        self.auto_hour.delete(0, "end")
        self.auto_hour.insert(0, str(settings.get("send_hour", 9)))
        self.auto_minute.delete(0, "end")
        self.auto_minute.insert(0, str(settings.get("send_minute", 0)))

        # 모드 (json | kakao_ocr) → 사용자 친화 라벨
        mode = settings.get("mode", "json")
        self.auto_mode_var.set(
            "카톡 친구탭 자동인식" if mode == "kakao_ocr" else "저장된 연락처"
        )

        # 템플릿 ID → 이름 변환
        bd_id = settings.get("birthday_template_id", "")
        an_id = settings.get("anniversary_template_id", "")
        bd_name = "(없음)"
        an_name = "(없음)"
        if self.orchestrator and bd_id:
            t = self.orchestrator.message_engine.get_template_by_id(bd_id)
            if t:
                bd_name = t.name
        if self.orchestrator and an_id:
            t = self.orchestrator.message_engine.get_template_by_id(an_id)
            if t:
                an_name = t.name
        self.bd_template_var.set(bd_name)
        self.an_template_var.set(an_name)
        self._update_auto_send_warning()

    def _update_auto_send_warning(self):
        """자동 발송 활성화 + 생일 템플릿 미선택 시 빨간 경고 표시."""
        if not hasattr(self, "auto_warn_label"):
            return
        enabled = self.auto_send_var.get()
        bd_name = self.bd_template_var.get() if hasattr(self, "bd_template_var") else "(없음)"
        if enabled and bd_name == "(없음)":
            self.auto_warn_label.configure(
                text="⚠ 생일 템플릿 미선택 — 자동 발송 안 됨"
            )
        else:
            self.auto_warn_label.configure(text="")

    def _save_auto_send_settings(self):
        """자동 발송 설정을 스케줄러에 저장"""
        if not self.orchestrator:
            return
        bd_name = self.bd_template_var.get()
        an_name = self.an_template_var.get()
        bd_id = self._template_id_map.get(bd_name, "")
        an_id = self._template_id_map.get(an_name, "")

        # 자동 발송 활성화 시 생일 템플릿 필수 검증
        if self.auto_send_var.get() and not bd_id:
            from tkinter import messagebox
            choice = messagebox.askyesno(
                "생일 템플릿 미선택",
                "자동 발송이 활성화되어 있는데 [생일 메시지 템플릿]이 선택되지 않았습니다.\n"
                "이대로 저장하면 생일 자동 발송이 동작하지 않습니다.\n\n"
                "그대로 저장하시겠습니까?\n"
                "(No 를 누르면 메시지 페이지에서 템플릿을 먼저 만드세요)",
            )
            if not choice:
                return  # 저장 취소 — 사용자가 템플릿 만들러 가게

        # 라벨 → 모드 코드
        mode_label = self.auto_mode_var.get()
        mode = "kakao_ocr" if mode_label == "카톡 친구탭 자동인식" else "json"

        self.orchestrator.scheduler.auto_send_settings = {
            "enabled": self.auto_send_var.get(),
            "mode": mode,
            "birthday_template_id": bd_id,
            "anniversary_template_id": an_id,
            "send_hour": int(self.auto_hour.get() or 9),
            "send_minute": int(self.auto_minute.get() or 0),
        }
        self.orchestrator.scheduler.save()

    # ── 세종텔레콤 ──

    def _test_sejong_connection(self):
        """세종텔레콤 DB 연결 테스트"""
        if not self.orchestrator:
            return
        config = self._get_sejong_config()
        result = self.orchestrator.init_sejong(config)
        if result.get("success"):
            self.sj_status_label.configure(text=result["message"], text_color=T.SUCCESS)
        else:
            self.sj_status_label.configure(text=result["message"], text_color=T.ERROR)

    def _save_sejong_env(self):
        """세종텔레콤 설정을 .env 파일에 저장"""
        if not self.orchestrator:
            return
        env_path = self.orchestrator.base_dir / ".env"
        lines = [
            "# 세종텔레콤 DB 연결 (알림톡/SMS 발송용)",
            f"SEJONG_DB_HOST={self.sj_db_host.get().strip()}",
            f"SEJONG_DB_PORT={self.sj_db_port.get().strip()}",
            f"SEJONG_DB_NAME={self.sj_db_name.get().strip()}",
            f"SEJONG_DB_USER={self.sj_db_user.get().strip()}",
            f"SEJONG_DB_PASSWORD={self.sj_db_password.get().strip()}",
            "",
            "# 카카오 알림톡 설정",
            f"SEJONG_SENDER_KEY={self.sj_sender_key.get().strip()}",
            f"SEJONG_CALLBACK={self.sj_callback.get().strip()}",
            f"SEJONG_TEMPLATE_CODE={self.sj_template_code.get().strip()}",
            "",
        ]
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _get_sejong_config(self) -> dict:
        """UI에서 세종텔레콤 설정 읽기"""
        return {
            "db": {
                "host": self.sj_db_host.get().strip(),
                "port": int(self.sj_db_port.get() or 3306),
                "name": self.sj_db_name.get().strip(),
                "user": self.sj_db_user.get().strip(),
                "password": self.sj_db_password.get().strip(),
            },
            "kakao": {
                "sender_key": self.sj_sender_key.get().strip(),
                "callback": self.sj_callback.get().strip(),
                "template_code": self.sj_template_code.get().strip(),
            }
        }

    # ── 설정 저장/로드 ──

    def _load_settings(self):
        if not self.orchestrator:
            return
        config = self.orchestrator.config
        kw = config.get("kakao_window", {})
        for entry, key, default in [
            (self.kakao_width, "width", 420), (self.kakao_height, "height", 700),
            (self.kakao_margin_r, "margin_right", 20), (self.kakao_margin_t, "margin_top", 40)
        ]:
            entry.delete(0, "end")
            entry.insert(0, str(kw.get(key, default)))

        sending = config.get("sending", {})
        for entry, key, default in [
            (self.delay_min, "delay_min", 30), (self.delay_max, "delay_max", 120),
            (self.retry_count, "retry_count", 2)
        ]:
            entry.delete(0, "end")
            entry.insert(0, str(sending.get(key, default)))

        # 계정 보호 설정 로드
        ad = config.get("anti_detect", {})
        for entry, key, default in [
            (self.action_delay_min, "action_delay_min", 0.3),
            (self.action_delay_max, "action_delay_max", 1.0),
            (self.rest_every, "rest_every", 15),
            (self.rest_min_s, "rest_min", 180),
            (self.rest_max_s, "rest_max", 420),
            (self.daily_limit_entry, "daily_limit", 150),
        ]:
            entry.delete(0, "end")
            entry.insert(0, str(ad.get(key, default)))

        # 카톡 → 연락처 DB 자동 반영 설정
        sync_cfg = config.get("auto_sync_birthday", {})
        if hasattr(self, "sync_bd_var"):
            self.sync_bd_var.set(sync_cfg.get("enabled", True))
        if hasattr(self, "sync_create_var"):
            self.sync_create_var.set(sync_cfg.get("create_new", False))

        # 세종텔레콤 설정 로드
        sj = config.get("sejong", {})
        sj_db = sj.get("db", {})
        sj_kakao = sj.get("kakao", {})
        for entry, val in [
            (self.sj_db_host, sj_db.get("host", "localhost")),
            (self.sj_db_port, str(sj_db.get("port", 3306))),
            (self.sj_db_name, sj_db.get("name", "sms")),
            (self.sj_db_user, sj_db.get("user", "")),
            (self.sj_db_password, sj_db.get("password", "")),
            (self.sj_sender_key, sj_kakao.get("sender_key", "")),
            (self.sj_callback, sj_kakao.get("callback", "")),
            (self.sj_template_code, sj_kakao.get("template_code", "")),
        ]:
            entry.delete(0, "end")
            entry.insert(0, str(val))

        # 저장된 좌표 로드
        positions = self._load_learned_positions()
        if positions and self.orchestrator:
            self.orchestrator.coordinates = positions

        # 자동 발송 설정 로드
        self._load_auto_send_settings()

    def _save_settings(self):
        if not self.orchestrator:
            return
        config = self.orchestrator.config
        config["kakao_window"] = {
            "width": int(self.kakao_width.get()),
            "height": int(self.kakao_height.get()),
            "margin_right": int(self.kakao_margin_r.get()),
            "margin_top": int(self.kakao_margin_t.get()),
        }
        config["sending"] = {
            "delay_min": int(self.delay_min.get()),
            "delay_max": int(self.delay_max.get()),
            "retry_count": int(self.retry_count.get()),
            "retry_delay": 5
        }
        config["ocr"] = {
            "language": self.ocr_lang.get(),
            "confidence_threshold": int(self.ocr_confidence.get())
        }
        # 기존 anti_detect 의 UI 노출 안 된 키 (warning_threshold, click_mode 등) 보존
        existing_ad = config.get("anti_detect", {})
        config["anti_detect"] = {
            **existing_ad,
            "action_delay_min": float(self.action_delay_min.get()),
            "action_delay_max": float(self.action_delay_max.get()),
            "rest_every": int(self.rest_every.get()),
            "rest_min": int(self.rest_min_s.get()),
            "rest_max": int(self.rest_max_s.get()),
            "daily_limit": int(self.daily_limit_entry.get()),
        }
        # 발송기에 즉시 반영
        if self.orchestrator and self.orchestrator.sender:
            sd = config["sending"]
            ad = config["anti_detect"]
            s = self.orchestrator.sender
            # 발송 간 딜레이
            s.delay_min = sd["delay_min"]
            s.delay_max = sd["delay_max"]
            s.retry_count = sd["retry_count"]
            # 계정 보호
            s.action_delay_min = ad["action_delay_min"]
            s.action_delay_max = ad["action_delay_max"]
            s.rest_every = ad["rest_every"]
            s.rest_min = ad["rest_min"]
            s.rest_max = ad["rest_max"]
            s.daily_limit = ad["daily_limit"]
        # 카톡 → 연락처 DB 자동 반영 설정 저장
        config["auto_sync_birthday"] = {
            "enabled": bool(self.sync_bd_var.get()) if hasattr(self, "sync_bd_var") else True,
            "create_new": bool(self.sync_create_var.get()) if hasattr(self, "sync_create_var") else False,
        }

        # 세종텔레콤: .env에 민감 정보 저장, config에는 비밀번호 제외
        self._save_sejong_env()
        sj = self._get_sejong_config()
        sj_safe = {
            "db": {
                "host": sj["db"]["host"],
                "port": sj["db"]["port"],
                "name": sj["db"]["name"],
                "user": sj["db"]["user"],
                "password": "",  # .env에만 저장
            },
            "kakao": {
                "sender_key": "",  # .env에만 저장
                "callback": sj["kakao"]["callback"],
                "template_code": sj["kakao"]["template_code"],
            }
        }
        config["sejong"] = sj_safe
        config_path = self.orchestrator.base_dir / "config" / "default_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 자동 발송 설정 저장
        self._save_auto_send_settings()

        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")
