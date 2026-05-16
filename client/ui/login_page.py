"""로그인 화면 — 이메일/비번 + 가입 토글 + 승인 대기 안내."""
import customtkinter as ctk
from auth import ApiClient, ApiError, SessionStore, get_hwid, get_hostname


class LoginWindow(ctk.CTk):
    """앱 시작 시 표시. 로그인 성공하면 on_success 콜백 → 메인 앱 전환."""

    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.session = SessionStore()
        self.api = ApiClient()

        self.title("TalkPC Pro — 로그인")
        self.geometry("420x500")
        self.resizable(False, False)

        self._mode = "login"
        self._build()

        # 저장된 세션 있으면 자동 진입 시도
        cached = self.session.load()
        if cached and cached.get("access_token"):
            self.api.token = cached["access_token"]
            self.after(100, lambda: self._auto_login(cached))

    def _build(self):
        ctk.CTkLabel(self, text="TalkPC Pro",
                      font=("Helvetica", 24, "bold")).pack(pady=(36, 4))
        self.subtitle = ctk.CTkLabel(self, text="로그인",
                                       font=("Helvetica", 13))
        self.subtitle.pack(pady=(0, 24))

        self.email = ctk.CTkEntry(self, placeholder_text="이메일",
                                    width=300, height=40)
        self.email.pack(pady=6)
        self.pw = ctk.CTkEntry(self, placeholder_text="비밀번호", show="•",
                                width=300, height=40)
        self.pw.pack(pady=6)

        self.submit_btn = ctk.CTkButton(self, text="로그인", width=300,
                                          height=44, command=self._submit)
        self.submit_btn.pack(pady=(20, 8))

        self.toggle_btn = ctk.CTkButton(
            self, text="계정이 없으신가요? 가입하기", width=300, height=32,
            fg_color="transparent", text_color="#58a6ff",
            hover=False, command=self._toggle_mode,
        )
        self.toggle_btn.pack()

        # 상태/에러 메시지
        self.status_label = ctk.CTkLabel(self, text="", text_color="#f85149",
                                           wraplength=320, justify="center")
        self.status_label.pack(pady=8)

        # 승인 대기 안내 (pending 상태일 때만 표시)
        self.pending_box = ctk.CTkFrame(self, fg_color="#1c2333",
                                          corner_radius=8)
        self.pending_label = ctk.CTkLabel(
            self.pending_box,
            text="",
            font=("Helvetica", 11), text_color="#fae100",
            wraplength=320, justify="center",
        )

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
        self.status_label.configure(text="")
        self.pending_box.pack_forget()

    def _show_pending(self, message: str, license_key: str = ""):
        """승인 대기 안내 박스 표시."""
        text = message
        if license_key:
            text += f"\n\n라이선스 키:\n{license_key}\n(관리자에게 전달)"
        self.pending_label.configure(text=text)
        self.pending_box.pack(fill="x", padx=40, pady=(8, 0))
        if not self.pending_label.winfo_ismapped():
            self.pending_label.pack(padx=16, pady=12)

    def _submit(self):
        email = self.email.get().strip()
        pw = self.pw.get()
        if not email or not pw:
            self.status_label.configure(text="이메일/비밀번호를 입력하세요.")
            return

        self.submit_btn.configure(state="disabled", text="처리 중...")
        self.status_label.configure(text="")
        self.pending_box.pack_forget()
        self.update()

        try:
            if self._mode == "signup":
                result = self.api.signup(email, pw)
                # 가입 직후엔 pending — 안내 표시 + 로그인 모드 전환
                self._show_pending(
                    "✓ 가입 완료. 관리자 승인 후 로그인 가능합니다.",
                    result.get("license_key", ""),
                )
                self._mode = "login"
                self.subtitle.configure(text="로그인")
                self.submit_btn.configure(state="normal", text="로그인")
                self.toggle_btn.configure(text="계정이 없으신가요? 가입하기")
                return

            # 로그인
            data = self.api.login(email, pw, hwid=get_hwid(),
                                    hostname=get_hostname())
            if data.get("access_token"):
                self.api.token = data["access_token"]
                self.session.save(
                    access_token=data["access_token"],
                    license_key=data["license_key"],
                    user_id=data["user_id"],
                    email=email,
                )
                self._proceed(data["license_key"])
            else:
                # status != active → 안내 후 종료
                self._show_pending(
                    data.get("status_message",
                              "계정을 사용할 수 없습니다."),
                    data.get("license_key", ""),
                )
                self.submit_btn.configure(state="normal", text="로그인")

        except ApiError as e:
            self.status_label.configure(text=str(e.message))
            self.submit_btn.configure(state="normal", text=(
                "가입하기" if self._mode == "signup" else "로그인"))

    def _auto_login(self, cached: dict):
        """캐시된 토큰으로 heartbeat → 성공이면 진입, 실패면 로그인 화면."""
        try:
            self.api.heartbeat(get_hwid())
            self._proceed(cached.get("license_key", ""))
        except ApiError as e:
            self.session.clear()
            if e.status == 403:
                self._show_pending(e.message,
                                     cached.get("license_key", ""))
        except Exception:
            self.session.clear()

    def _proceed(self, license_key: str):
        self.destroy()
        self.on_success(api=self.api, license_key=license_key)
