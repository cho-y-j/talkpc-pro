"""로그인 화면 — 이메일/비밀번호 입력, 가입 토글."""
import customtkinter as ctk
from tkinter import messagebox

from auth import ApiClient, SessionStore, get_hwid
from auth.hwid import get_hostname


class LoginWindow(ctk.CTk):
    """앱 시작 시 표시. 로그인 성공하면 on_success 콜백 → 메인 앱 전환."""

    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.session = SessionStore()
        self.api = ApiClient()

        self.title("TalkPC Pro — 로그인")
        self.geometry("400x420")
        self.resizable(False, False)

        self._mode = "login"  # "login" | "signup"
        self._build()

        # 저장된 세션 있으면 즉시 진입 시도
        cached = self.session.load()
        if cached and cached.get("access_token"):
            self.api.token = cached["access_token"]
            self.after(100, lambda: self._auto_login(cached))

    def _build(self):
        ctk.CTkLabel(self, text="TalkPC Pro",
                      font=("Helvetica", 22, "bold")).pack(pady=(40, 4))
        self.subtitle = ctk.CTkLabel(self, text="로그인",
                                       font=("Helvetica", 13))
        self.subtitle.pack(pady=(0, 24))

        self.email = ctk.CTkEntry(self, placeholder_text="이메일",
                                    width=280, height=40)
        self.email.pack(pady=6)
        self.pw = ctk.CTkEntry(self, placeholder_text="비밀번호", show="•",
                                width=280, height=40)
        self.pw.pack(pady=6)

        self.submit_btn = ctk.CTkButton(self, text="로그인", width=280,
                                          height=44, command=self._submit)
        self.submit_btn.pack(pady=(20, 8))

        self.toggle_btn = ctk.CTkButton(
            self, text="계정이 없으신가요? 가입하기", width=280, height=32,
            fg_color="transparent", text_color="#58a6ff",
            hover=False, command=self._toggle_mode,
        )
        self.toggle_btn.pack()

        self.status = ctk.CTkLabel(self, text="", text_color="#f85149")
        self.status.pack(pady=8)

    def _toggle_mode(self):
        if self._mode == "login":
            self._mode = "signup"
            self.subtitle.configure(text="가입")
            self.submit_btn.configure(text="가입하기")
            self.toggle_btn.configure(text="이미 계정이 있으신가요? 로그인")
        else:
            self._mode = "login"
            self.subtitle.configure(text="로그인")
            self.submit_btn.configure(text="로그인")
            self.toggle_btn.configure(text="계정이 없으신가요? 가입하기")
        self.status.configure(text="")

    def _submit(self):
        email = self.email.get().strip()
        pw = self.pw.get()
        if not email or not pw:
            self.status.configure(text="이메일/비밀번호를 입력하세요.")
            return

        self.submit_btn.configure(state="disabled", text="처리 중...")
        self.update()
        try:
            if self._mode == "signup":
                self.api.signup(email, pw)  # 가입 후 즉시 로그인 흐름
            data = self.api.login(email, pw, hwid=get_hwid(),
                                    hostname=get_hostname())
            self.api.token = data["access_token"]
            self.session.save(
                access_token=data["access_token"],
                license_key=data["license_key"],
                user_id=data["user_id"],
                email=email,
            )
            self._proceed(data["license_key"])
        except Exception as e:
            self.status.configure(text=str(e))
            self.submit_btn.configure(state="normal", text=(
                "가입하기" if self._mode == "signup" else "로그인"))

    def _auto_login(self, cached: dict):
        """캐시된 토큰으로 health 체크 → 성공이면 즉시 진입, 실패면 로그인 화면."""
        try:
            self.api.health()
            self._proceed(cached.get("license_key", ""))
        except Exception:
            self.session.clear()  # 토큰 만료

    def _proceed(self, license_key: str):
        self.destroy()
        self.on_success(api=self.api, license_key=license_key)
