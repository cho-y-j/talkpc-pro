"""
Theme - 다크 모드 모던 테마 설정
"""


class AppTheme:
    """앱 테마 색상 및 폰트"""

    # -- 메인 컬러 --
    BG_DARK = "#0d1117"        # 최상위 배경
    BG_SIDEBAR = "#161b22"     # 사이드바
    BG_CARD = "#1c2333"        # 카드/패널
    BG_INPUT = "#21262d"       # 입력 필드
    BG_HOVER = "#30363d"       # 호버 상태

    # -- 액센트 --
    ACCENT = "#fae100"         # 카카오 옐로우
    ACCENT_HOVER = "#ffe033"
    ACCENT_DIM = "#b39e00"

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

    # -- 보더 --
    BORDER = "#30363d"
    BORDER_ACTIVE = "#58a6ff"

    # -- 카테고리 컬러 --
    CATEGORY_COLORS = {
        "friend": "#58a6ff",
        "family": "#f85149",
        "business": "#fae100",
        "vip": "#bc8cff",
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
