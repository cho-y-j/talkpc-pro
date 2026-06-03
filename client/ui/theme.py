"""
Theme - 다크 모드 모던 테마 설정
"""


class AppTheme:
    """앱 테마 색상 및 폰트 — 통일 팔레트 (v0.1.11).

    배경: GitHub-dark 계열 (warm #181c24~#30363d). 액센트: 카카오 옐로우
    살짝 톤다운(#f0b90b — 강한 #fae100 보다 눈 피로 ↓). 페이지별 임의
    색상(#e67e22/#8e44ad 등) 추방하고 의미별로만(POSITIVE/PRIMARY) 사용.
    """

    # -- 메인 컬러 --
    BG_DARK = "#0d1117"        # 최상위 배경
    BG_SIDEBAR = "#161b22"     # 사이드바
    BG_CARD = "#1c2333"        # 카드/패널
    BG_INPUT = "#21262d"       # 입력 필드
    BG_HOVER = "#30363d"       # 호버 상태

    # -- 액센트 (메인 CTA — 카카오 옐로우 톤다운) --
    ACCENT = "#f0b90b"         # 카카오 옐로우(soft) — 강한 #fae100 대신
    ACCENT_HOVER = "#ffc933"
    ACCENT_DIM = "#a8830a"

    # -- 액션 컬러 (페이지별 임의 RGB 대신 이 4가지만 사용) --
    ACTION_POSITIVE = "#3fb950"    # 카톡친구 수집·실행 등 긍정/실행
    ACTION_POSITIVE_HOVER = "#2ea043"
    ACTION_FEATURE = "#d97757"     # 생일발송 등 부가기능 (warm coral)
    ACTION_FEATURE_HOVER = "#b85e3f"
    ACTION_SCHEDULE = "#a371f7"    # 매일자동 등 스케줄 (soft purple)
    ACTION_SCHEDULE_HOVER = "#8957e5"
    ACTION_DANGER = "#f85149"      # 삭제 등 위험
    ACTION_DANGER_HOVER = "#da3633"

    # -- 상태 컬러 --
    SUCCESS = "#3fb950"        # 성공 (초록)
    ERROR = "#f85149"          # 실패 (빨강)
    WARNING = "#d29922"        # 경고 (주황)
    INFO = "#58a6ff"           # 정보 (파랑)

    # -- 텍스트 --
    TEXT_PRIMARY = "#f0f6fc"   # 주요 텍스트
    TEXT_SECONDARY = "#8b949e" # 보조 텍스트
    TEXT_MUTED = "#484f58"     # 희미한 텍스트
    TEXT_ON_ACCENT = "#1a1a1a" # 액센트 위 텍스트
    TEXT_ON_DARK = "#ffffff"   # 컬러 버튼 위 흰 텍스트

    # -- 보더 --
    BORDER = "#30363d"
    BORDER_ACTIVE = "#58a6ff"

    # -- 카테고리 컬러 --
    CATEGORY_COLORS = {
        "friend": "#58a6ff",
        "family": "#f85149",
        "business": "#f0b90b",
        "vip": "#a371f7",
        "other": "#8b949e"
    }

    # -- 폰트 --
    FONT_FAMILY = "맑은 고딕"  # Windows
    FONT_FAMILY_MAC = "Apple SD Gothic Neo"
    FONT_SIZE_TITLE = 18
    FONT_SIZE_HEADER = 14
    FONT_SIZE_BODY = 12
    FONT_SIZE_SMALL = 10
    FONT_SIZE_TINY = 9

    # -- 사이즈 --
    SIDEBAR_WIDTH = 220
    CARD_RADIUS = 8
    CARD_PADDING = 16
    BUTTON_HEIGHT = 36

    @classmethod
    def get_font_family(cls):
        import platform
        if platform.system() == "Darwin":
            return cls.FONT_FAMILY_MAC
        return cls.FONT_FAMILY
