"""
KakaoFriends - 카카오톡 친구 탭 자동화 헬퍼

핵심 원리:
- 절대 좌표 기억 X — 매 사이클마다 스크린샷 + OCR 로 위치 재탐색
- 헤더 카운터 (생일인 친구 N, 친구 N) 로 종료 시점 결정
- 시각적 앵커 ("선물하기" 버튼 등) 로 행 위치 식별
- 스크롤은 WM_MOUSEWHEEL PostMessage (커서 이동 없음)

용도:
1. 생일자 자동 카톡 발송
2. 친구 목록 자동 수집 (주소록 생성)
"""

import asyncio
import io
import re
import time
from typing import Optional

try:
    import win32api
    import win32con
    import win32gui
except ImportError:
    win32api = None

# Windows.Media.Ocr (한국어 화면 OCR) - 한국 Windows 10/11 에 내장
_WIN_OCR_AVAILABLE = False
try:
    import winrt.windows.media.ocr as _wocr
    import winrt.windows.globalization as _wglob
    import winrt.windows.graphics.imaging as _wimg
    import winrt.windows.storage.streams as _wstreams
    _WIN_OCR_AVAILABLE = True
except ImportError:
    pass

# PaddleOCR (한국어 화면 OCR, 95%+ 정확도)
# 모델 경로는 반드시 ASCII (Paddle C++ 가 한글 경로 못 읽음)
_PADDLE_OCR = None
_PADDLE_AVAILABLE = False
_PaddleOCRClass = None
_PADDLE_IMPORT_ERROR = None  # 진단용 — import 실패 시 원인 문자열 보존
try:
    from paddleocr import PaddleOCR as _PaddleOCRClass
    _PADDLE_AVAILABLE = True
except Exception as _e:
    # ImportError 외에도 FileNotFoundError 등 (PyInstaller 미수집 .py)
    # 폭넓게 catch — Paddle 못 쓰면 Tesseract 폴백.
    import traceback as _tb
    _PADDLE_IMPORT_ERROR = f"{_e!r}\n{_tb.format_exc()}"


def _diag(msg):
    """OCR 진단 로그 — kakao_win32._log 재사용 (%TEMP%/kakao_win32_debug.log)."""
    try:
        from core.kakao_win32 import _log
        _log(f"[OCR] {msg}")
    except Exception:
        pass


_PADDLE_INIT_LOGGED = False  # 실패 로그를 매 행마다 도배하지 않도록 1회만


def _get_paddle_ocr():
    """PaddleOCR 인스턴스 lazy 초기화 (모듈 레벨 캐싱).
    모델은 paddle_models/ 디렉토리에서 로드 (ASCII 경로 강제).
    """
    global _PADDLE_OCR, _PADDLE_INIT_LOGGED
    if _PADDLE_OCR is not None:
        return _PADDLE_OCR
    if not _PADDLE_AVAILABLE:
        if not _PADDLE_INIT_LOGGED:
            _diag(f"paddleocr import 실패 → 폴백 OCR 사용. 원인: {_PADDLE_IMPORT_ERROR}")
            _PADDLE_INIT_LOGGED = True
        return None

    import os
    import sys
    # paddle_models 위치 우선순위:
    #   1. exe 옆 (사용자가 같이 배포 / dev 환경 PROJECT_ROOT)
    #   2. PyInstaller onefile 임시 폴더 (_MEIPASS) — spec 의 datas 로 번들된 경우
    #   3. exe 의 _internal/ (onedir 모드)
    candidates = [os.path.abspath("paddle_models")]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "paddle_models"))
        candidates.append(os.path.join(
            os.path.dirname(sys.executable), "_internal", "paddle_models"
        ))

    base = None
    for c in candidates:
        det_test = os.path.join(c, "det", "Multilingual_PP-OCRv3_det_infer")
        rec_test = os.path.join(c, "rec", "korean_PP-OCRv4_rec_infer")
        if os.path.exists(det_test) and os.path.exists(rec_test):
            base = c
            break

    if base is None:
        # 모델 파일이 없으면 사용 불가 (paddle_models 디렉토리 누락)
        if not _PADDLE_INIT_LOGGED:
            _diag(f"paddle_models 못 찾음 → 폴백 OCR. 탐색 경로: {candidates}")
            _PADDLE_INIT_LOGGED = True
        return None

    det_dir = os.path.join(base, "det", "Multilingual_PP-OCRv3_det_infer")
    rec_dir = os.path.join(base, "rec", "korean_PP-OCRv4_rec_infer")
    # cls 모델도 번들에서 명시 지정. 안 주면 paddleocr 가 use_angle_cls=False
    # 여도 ~/.paddleocr 캐시 검사 → 없으면 baidu CDN 다운로드 시도 → tqdm 이
    # console=False frozen exe 에서 sys.stdout=None 으로 죽음. (고객 PC 사고
    # 직접 원인). 번들 cls 경로 주면 다운로드 자체를 안 함.
    cls_dir = os.path.join(base, "cls", "ch_ppocr_mobile_v2.0_cls_infer")

    try:
        import warnings
        warnings.filterwarnings("ignore")
        _PADDLE_OCR = _PaddleOCRClass(
            use_angle_cls=False,
            lang="korean",
            det_model_dir=det_dir,
            rec_model_dir=rec_dir,
            cls_model_dir=cls_dir,
            show_log=False,
            # 작은 카톡 폰트 검출률 향상 — 임계값 낮춤
            det_db_thresh=0.2,        # 기본 0.3 → 0.2 (텍스트 영역 더 적극 검출)
            det_db_box_thresh=0.5,    # 기본 0.6 → 0.5 (박스 신뢰 임계 완화)
            det_db_unclip_ratio=2.0,  # 기본 1.5 → 2.0 (박스 여유 확대)
        )
        _diag(f"PaddleOCR 초기화 성공 (모델: {base})")
        return _PADDLE_OCR
    except Exception as e:
        # ★ frozen exe 에서 paddle 런타임 실패의 핵심 원인이 여기 잡힘.
        #   (DLL 로드 실패, paddle.base import 오류 등) — 전체 traceback 기록.
        if not _PADDLE_INIT_LOGGED:
            import traceback
            _diag(f"PaddleOCR 초기화 실패 → 폴백 OCR. 원인: {e!r}\n{traceback.format_exc()}")
            _PADDLE_INIT_LOGGED = True
        return None


# WM_MOUSEWHEEL 휠 한 칸 = WHEEL_DELTA (120)
WHEEL_DELTA = 120


# 한국 성씨 화이트리스트 — OCR 결과 첫 글자가 이 안에 없으면 보정 시도
# (인구 분포 95%+ 커버. 희성은 보정 안 됨 — 사용자 수동 수정)
KOREAN_SURNAMES = set(
    "김이박최정강조윤장임한신오서권황안송류전홍고문양손배백허유남심노"
    "하곽성차주우구나라진채변마도명천함추표소공원사방왕팽위반석탁여"
    "맹승옥진봉장경홍필철노연라음복엄음국황경명국황표진감채라사도용"
    "탁복형복음필인하단형사은당단변섭빈단연용지편좌난기교을근총조옹"
    "두원동매소맹비완태엽편풍포감강견경계곡고관광굉구궁궐근금기길나"
    "남낭내노녹뇌니단담당대도독돈동두라란량려렬렴례로뢰료룡루류륙륜"
    "륭률리림마매맥맹면명모목몽묘무묵문미민박반방배백번범변별병보복"
    "봉부분비빈빙사삭산상서석선설섭성세소속손송수숙순승시신실심아악"
    "안애야양어엄여연염엽영예오옥온옹완왕외요용우운원위유육윤은음의"
    "이인일임자장재저전점정제조족존종좌주준중지직진집차창채천첨청초"
    "최추춘출충치침칠탁태택토통팽편평포표필하한함해향현형호화환황회"
)

# 자주 혼동되는 OCR 오인 → 성씨 보정 매핑
# 키: 잘못 인식된 첫 글자 (성씨 화이트리스트에 없음)
# 값: 보정 후보 (가장 흔한 정정 우선)
SURNAME_CONFUSION_FIX = {
    "감": "강",   # 받침 ㅁ → ㅇ
    "곤": "곽",   # 곤은 희성, 곽이 흔함
    "광": "곽",   # 받침 ㅇ → ㄱ
    "과": "곽",   # 받침 없음 → ㄱ
    "괄": "곽",
    "긴": "김",
    "긱": "김",
    "잉": "임",
    "잎": "임",
    "옷": "오",
    "쇠": "최",
    "죄": "최",
    "젱": "정",
    "젊": "정",
    "헐": "허",
    "윕": "윤",
    "솜": "송",
    "잔": "장",
    "딘": "신",
}


def _correct_surname(name: str) -> str:
    """이름 첫 글자가 한국 성씨 화이트리스트에 없으면 OCR 혼동 보정 시도."""
    if not name or len(name) < 2:
        return name
    first = name[0]
    if first in KOREAN_SURNAMES:
        return name
    if first in SURNAME_CONFUSION_FIX:
        corrected = SURNAME_CONFUSION_FIX[first] + name[1:]
        return corrected
    # 화이트리스트에도 없고 보정 사전에도 없음 — 그대로 (희성일 수도)
    return name


def _makelparam(x: int, y: int) -> int:
    """LPARAM 패킹 (좌표용)"""
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


class TextHit:
    """OCR 검출 결과 한 항목 (절대 좌표)"""
    def __init__(self, text: str, abs_x: int, abs_y: int,
                 width: int, height: int, confidence: int):
        self.text = text
        self.x = abs_x
        self.y = abs_y
        self.width = width
        self.height = height
        self.confidence = confidence
        self.cx = abs_x + width // 2
        self.cy = abs_y + height // 2

    def __repr__(self):
        return f"<TextHit {self.text!r} @({self.x},{self.y}) conf={self.confidence}>"


class KakaoFriends:
    """카카오톡 친구 탭 자동화 헬퍼"""

    # 섹션 헤더 키워드 (OCR이 한 글자 깨져도 매칭되도록 부분 키워드 사용)
    SECTION_BIRTHDAY = ["생일인", "생밀인", "생일"]
    SECTION_FRIENDS = ["친구", "진구"]
    SECTION_CHANNEL = ["채널"]
    SECTION_UPDATED = ["업데이트한", "업데이트"]
    SECTION_FAVORITE = ["즐겨찾는", "즐겨찾"]  # 즐겨찾는 친구 섹션 (친구 목록 위)

    def __init__(self, win32_engine, ocr_engine, screen_capture):
        """
        Args:
            win32_engine: KakaoWin32 인스턴스 (find_main_window 호출됨 상태)
            ocr_engine: OCREngine 인스턴스
            screen_capture: ScreenCapture 인스턴스
        """
        self.win32 = win32_engine
        self.ocr = ocr_engine
        self.capture = screen_capture
        # 생일 발송 시 sender 의 검증된 send_to_current_selection 사용용.
        # orchestrator 가 KakaoFriends 생성 후 set_sender() 로 주입.
        self.sender = None

    def set_sender(self, sender):
        """KakaoSender 주입 — 검증된 chat_hwnd / 좌표 클릭 발송 사용."""
        self.sender = sender

    # ── 카카오 메인 창 캡처 ──

    def get_window_rect(self) -> Optional[dict]:
        """카카오 메인 창 절대 좌표"""
        if not self.win32.main_hwnd:
            self.win32.find_main_window()
        return self.win32.get_window_rect(self.win32.main_hwnd)

    def capture_window(self) -> Optional["Image.Image"]:
        """카카오 메인 창 영역만 스크린샷"""
        rect = self.get_window_rect()
        if not rect:
            return None
        return self.capture.capture_kakao_window(rect)

    # ── OCR 기반 텍스트 위치 탐색 ──

    def find_text_hits(self, image=None) -> list[TextHit]:
        """
        카카오톡 창에서 모든 인식된 텍스트의 절대 좌표 리스트 반환.

        Paddle 단일 엔진. 행 OCR 의 95% 파이프라인(preprocess_for_paddle 5x)
        은 행 크롭 전용이라 전체창엔 부적절 → 전체창은 가벼운 2x 전처리.

        Returns:
            list[TextHit] - y 좌표 오름차순 정렬
        """
        rect = self.get_window_rect()
        if not rect:
            return []

        if image is None:
            image = self.capture_window()
            if image is None:
                return []

        return self._find_text_hits_paddle(image, rect)

    def _find_text_hits_paddle(self, image, rect) -> list:
        """Paddle 전체창 OCR → TextHit 리스트.

        ★ preprocess_for_paddle 의 5x 는 행 크롭(약 200×50→1000×250) 에 튜닝됨.
          전체창(420×700→2100×3500) 에 그대로 쓰면 detection 실패 → 전체창은
          별도 가벼운 2x 전처리 (회색조 + 약한 대비) 사용.
          행 OCR 의 95% 파이프라인(_paddle_ocr_row)은 영향 없음.
        """
        try:
            from core.paddle_ocr_helper import get_paddle_ocr
        except Exception:
            return []
        paddle = get_paddle_ocr()
        if paddle is None:
            return []
        try:
            import numpy as np
        except ImportError:
            return []

        from PIL import Image as _PILImage, ImageEnhance
        SCALE = 2
        big = image.resize(
            (image.width * SCALE, image.height * SCALE),
            _PILImage.LANCZOS,
        )
        gray = big.convert("L")
        contrasted = ImageEnhance.Contrast(gray).enhance(1.3)
        pre = contrasted.convert("RGB")

        try:
            result = paddle.ocr(np.array(pre), cls=False)
        except Exception:
            return []
        if not result or not result[0]:
            return []

        hits = []
        for entry in result[0]:
            try:
                box, (text, conf) = entry
            except (ValueError, TypeError):
                continue
            text = (text or "").strip()
            if not text or conf < 0.5:
                continue
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            x_min = int(min(xs)) // SCALE
            y_min = int(min(ys)) // SCALE
            w = (int(max(xs)) - int(min(xs))) // SCALE
            h = (int(max(ys)) - int(min(ys))) // SCALE
            hits.append(TextHit(
                text=text,
                abs_x=rect["x"] + x_min,
                abs_y=rect["y"] + y_min,
                width=max(w, 1),
                height=max(h, 1),
                confidence=int(conf * 100),
            ))

        hits.sort(key=lambda h: (h.y, h.x))
        return hits

    def find_text(self, keywords: list[str], hits=None) -> Optional[TextHit]:
        """
        키워드 중 하나라도 부분 매칭되는 첫 번째 텍스트 위치 반환

        OCR 글자 깨짐 대응을 위해 부분/유사 매칭:
          - 키워드가 텍스트에 포함되면 매칭
          - 텍스트가 키워드에 포함되어도 매칭 (한 글자 깨짐 케이스)
        """
        if hits is None:
            hits = self.find_text_hits()

        for h in hits:
            t = h.text.strip()
            for kw in keywords:
                if kw in t or t in kw:
                    return h
        return None

    def find_all_text(self, keywords: list[str], hits=None) -> list[TextHit]:
        """키워드 매칭되는 모든 텍스트 위치 반환"""
        if hits is None:
            hits = self.find_text_hits()

        result = []
        for h in hits:
            t = h.text.strip()
            for kw in keywords:
                if kw in t or (t and t in kw):
                    result.append(h)
                    break
        return result

    # ── 섹션 헤더 + 카운터 ──

    def get_section_count(self, section_keywords: list[str], hits=None) -> Optional[dict]:
        """
        섹션 헤더 위치 + 그 옆의 숫자(카운터) 추출

        예) "생일인 친구 3" → {"header_hit": <TextHit>, "count": 3, "number_hit": <TextHit>}
            "친구 714" → {"header_hit": ..., "count": 714, "number_hit": ...}

        OCR 결과에서 키워드를 찾고, 같은 줄(±10px) 의 숫자를 매칭
        """
        if hits is None:
            hits = self.find_text_hits()

        header = self.find_text(section_keywords, hits=hits)
        if not header:
            return None

        # 같은 줄 (y 좌표 ±15px 이내) 의 우측에 있는 숫자 찾기
        Y_TOLERANCE = 15
        same_line_numbers = []
        for h in hits:
            if abs(h.cy - header.cy) <= Y_TOLERANCE and h.x > header.x:
                m = re.search(r"\d+", h.text)
                if m:
                    same_line_numbers.append((h, int(m.group())))

        if not same_line_numbers:
            return {"header_hit": header, "count": None, "number_hit": None}

        # 같은 줄의 가장 큰 숫자 채택 (1~2자리 노이즈 OCR 방지)
        # 카톡 카운터는 생일 1~9명, 친구 수십~수천 명 범위라
        # 작은 노이즈 숫자보다 큰 쪽이 정답일 확률이 매우 높음
        same_line_numbers.sort(key=lambda x: x[1], reverse=True)
        nh, count = same_line_numbers[0]
        return {"header_hit": header, "count": count, "number_hit": nh}

    def get_birthday_count(self, hits=None) -> Optional[int]:
        """생일인 친구 수 (없으면 None)"""
        info = self.get_section_count(self.SECTION_BIRTHDAY, hits=hits)
        return info["count"] if info else None

    # 광고 배너 영역 비율 (창 높이 대비) — 무료 카톡 하단 광고
    AD_AREA_RATIO = 0.85

    def get_friend_count(self, hits=None) -> Optional[int]:
        """
        친구 N 수 추정.

        견고한 휴리스틱 (정확도 우선):
          1) "친구" 헤더 텍스트가 실제 OCR로 잡혔으면 → 같은 줄 가장 큰 숫자
             (단, 첫 줄의 탭 헤더 "친구" 와 안내문 "친구의 생일을..." 은 제외)
          2) 카톡 무료 사용자의 광고 배너 영역(y > 85%) 의 숫자는 무조건 제외
             → 광고의 "234", "1000원" 같은 노이즈가 친구 카운터로 잘못 잡히는 것 방지
          3) 친구 헤더가 화면 밖 (광고에 가려졌거나 스크롤 밖) 이면 None 반환
             → 거짓 양성 방지. 사용자가 카톡 창 광고 위로 스크롤한 후 다시 호출하거나
               UI 에서 직접 입력하도록 유도
        """
        if hits is None:
            hits = self.find_text_hits()

        rect = self.get_window_rect()
        if not rect:
            return None

        # 광고 영역 y 임계값
        ad_y_threshold = rect["y"] + int(rect["height"] * self.AD_AREA_RATIO)

        # 다른 섹션 카운터/헤더 y 추출 (친구 헤더보다 위에 있는 것들)
        excluded = set()
        last_other_header_y = 0
        for kws in (self.SECTION_BIRTHDAY, self.SECTION_UPDATED, self.SECTION_CHANNEL):
            info = self.get_section_count(kws, hits=hits)
            if info:
                if info.get("count") is not None:
                    excluded.add(info["count"])
                if info.get("header_hit"):
                    last_other_header_y = max(last_other_header_y, info["header_hit"].y)

        # "친구" 헤더 후보: 다른 모든 섹션 헤더보다 아래, 광고보다 위, 본문 텍스트 아닌 짧은 키워드
        friend_header_candidates = []
        for h in hits:
            t = h.text.strip()
            if t in ("친구", "진구", "친 구", "진 구"):
                if h.y > last_other_header_y and h.y < ad_y_threshold:
                    friend_header_candidates.append(h)

        if not friend_header_candidates:
            # 친구 헤더 자체를 못 잡음 → 신뢰할 수 없음
            return None

        # 가장 위쪽 친구 헤더 (혹 여러 개 잡혔으면)
        friend_header = min(friend_header_candidates, key=lambda x: x.y)

        # 같은 줄 (±15px) 의 숫자 후보, 광고 영역 제외, 다른 섹션 카운터 제외
        Y_TOL = 15
        candidates = []
        for h in hits:
            if abs(h.cy - friend_header.cy) > Y_TOL:
                continue
            if h.x <= friend_header.x:
                continue
            if h.y >= ad_y_threshold:
                continue
            for m in re.finditer(r"\d+", h.text):
                n = int(m.group())
                if 1 <= n <= 100000 and n not in excluded:
                    candidates.append(n)

        if not candidates:
            return None
        return max(candidates)

    # ── "선물하기" 버튼 탐지 ──

    def find_gift_buttons(self, hits=None) -> list[TextHit]:
        """
        "선물하기" 버튼 위치 리스트 (생일자 행 식별용)

        OCR 글자 분리 대응:
          best 모델에서도 '선물하기' → '선'+'물'+'하기' 또는 '하'+'기' 분리됨
          전략: 화면 우측(>65%) 영역에서 같은 행(y±10) 의 짧은 텍스트들을 그룹화
                선/물/하/기 부분 글자가 그룹 내에 1개라도 있으면 → 선물하기 버튼
        """
        if hits is None:
            hits = self.find_text_hits()

        rect = self.get_window_rect()
        if not rect:
            return []
        right_threshold = rect["x"] + int(rect["width"] * 0.65)

        # 우측 영역의 짧은 한글 텍스트만 (긴 메시지 텍스트 배제)
        right_hits = [
            h for h in hits
            if h.x >= right_threshold and len(h.text) <= 4
        ]

        # 같은 행 그룹화 (y ±10px)
        Y_TOL = 10
        groups = []  # [{"y": int, "items": [TextHit]}]
        for h in sorted(right_hits, key=lambda x: x.y):
            placed = False
            for g in groups:
                if abs(h.y - g["y"]) <= Y_TOL:
                    g["items"].append(h)
                    g["y"] = sum(i.y for i in g["items"]) // len(g["items"])
                    placed = True
                    break
            if not placed:
                groups.append({"y": h.y, "items": [h]})

        # 그룹 내에 선/물/하/기 중 하나라도 있고 텍스트 합치면 선물하기 의미하면 버튼
        gift_chars = set("선물하기")
        result = []
        for g in groups:
            combined = "".join(i.text for i in sorted(g["items"], key=lambda x: x.x))
            combined_chars = set(combined)
            # 선/물/하/기 글자 2개 이상 포함 → 선물하기 버튼으로 인정
            overlap = combined_chars & gift_chars
            if len(overlap) >= 2 or "선물" in combined or "하기" in combined:
                # 그룹 좌측 위치를 버튼 위치로
                left_most = min(g["items"], key=lambda x: x.x)
                result.append(TextHit(
                    text=combined,
                    abs_x=left_most.x,
                    abs_y=g["y"],
                    width=sum(i.width for i in g["items"]),
                    height=left_most.height,
                    confidence=int(sum(i.confidence for i in g["items"]) / len(g["items"])),
                ))

        result.sort(key=lambda x: x.y)
        return result

    # ── 생일자 행 좌표 추정 ──

    # 행 시점 라벨 (카톡 생일 섹션은 ±2일 보여줌)
    DAY_TODAY = ["오늘"]
    DAY_YESTERDAY = ["어제", "그제"]
    DAY_TOMORROW = ["내일", "모레"]
    # 호환용 — 어제/내일 합쳐 검사하는 기존 코드 경로
    DAY_OTHER = DAY_YESTERDAY + DAY_TOMORROW

    def _classify_row_day(self, row_y: int, hits: list,
                           y_tolerance: int = 25) -> str:
        """
        행의 시점 분류. 행 y 기준 ±tolerance 범위 내 텍스트 검사.
        Returns: "today" | "other" | "unknown"
        """
        same_row = [h for h in hits if abs(h.y - row_y) <= y_tolerance]

        for h in same_row:
            for kw in self.DAY_TODAY:
                if kw in h.text:
                    return "today"
        for h in same_row:
            for kw in self.DAY_OTHER:
                if kw in h.text:
                    return "other"
        return "unknown"

    def find_birthday_rows(self, expected_count: int = None,
                            today_only: bool = False,
                            hits=None) -> list[dict]:
        """
        생일자 행들의 클릭 좌표 추정.

        전략:
          1) "선물하기" 버튼들 위치 → 각 버튼 좌측이 행 클릭 영역 (이름/프로필 클릭)
          2) 부족하면 행 높이 추정 후 N 개로 보간
          3) today_only=True 면 "오늘" 텍스트가 같은 행에 있는 행만 반환

        Args:
            expected_count: 헤더에서 읽은 N (생일 섹션 전체 인원)
            today_only: True 면 오늘 생일자만 (어제/내일 제외)

        Returns:
            [{"y", "click_x", "click_y", "method": "ocr"|"interpolated",
              "day": "today"|"other"|"unknown"}, ...]
        """
        if hits is None:
            hits = self.find_text_hits()

        rect = self.get_window_rect()
        if not rect:
            return []

        # 행 클릭 영역: 프로필이미지 우측 ~ 선물하기 버튼 좌측 사이 (이름 영역)
        click_x = rect["x"] + int(rect["width"] * 0.35)

        # 1) 선물하기 버튼 위치들로 행 추정
        gift_btns = self.find_gift_buttons(hits=hits)
        rows = [
            {"y": g.y, "click_x": click_x, "click_y": g.cy, "method": "ocr"}
            for g in gift_btns
        ]

        # 2) 보간 — N 개 미달이고 최소 2개 행이 잡혔으면 행 높이 추정
        if expected_count and len(rows) >= 2 and len(rows) < expected_count:
            ys = sorted([r["y"] for r in rows])
            diffs = [ys[i+1] - ys[i] for i in range(len(ys) - 1)]
            row_height = min(diffs) if diffs else 56

            first_y = ys[0]
            existing_ys = set(ys)
            for i in range(expected_count):
                target_y = first_y + i * row_height
                if any(abs(target_y - ey) < 15 for ey in existing_ys):
                    continue
                rows.append({
                    "y": target_y,
                    "click_x": click_x,
                    "click_y": target_y + row_height // 2,
                    "method": "interpolated",
                })
                existing_ys.add(target_y)

        # 3) y 정렬 + N 으로 자르기
        rows.sort(key=lambda r: r["y"])
        if expected_count:
            rows = rows[:expected_count]

        # 4) 시점 분류 + 필터
        for row in rows:
            row["day"] = self._classify_row_day(row["y"], hits)

        if today_only:
            rows = [r for r in rows if r["day"] == "today"]

        return rows

    def find_today_birthday_rows(self, expected_count: int = None,
                                  hits=None) -> list[dict]:
        """오늘 생일자 행만 (어제/내일 제외, '오늘' 텍스트로 필터)"""
        return self.find_birthday_rows(
            expected_count=expected_count,
            today_only=True,
            hits=hits,
        )

    # ── 스크롤 (WM_MOUSEWHEEL PostMessage) ──

    def scroll_at(self, abs_x: int, abs_y: int, ticks: int = -3):
        """
        지정 좌표에 마우스 휠 이벤트 전송 (커서 이동 없음)

        Args:
            abs_x, abs_y: 휠을 굴릴 절대 좌표 (스크롤 가능 영역 내)
            ticks: 휠 단위. 음수=아래, 양수=위. -3 ≈ 한 화면의 일부 정도
        """
        if not win32api:
            return

        # 메인 창에 메시지 전달
        hwnd = self.win32.main_hwnd
        if not hwnd:
            return

        # WM_MOUSEWHEEL 의 lParam 은 스크린 좌표 사용 (특이점)
        wparam = (ticks * WHEEL_DELTA) << 16  # 상위 16비트가 wheel delta
        # 부호 처리 (음수면 0xFFFF 마스크 후 시프트)
        wheel_amount = ticks * WHEEL_DELTA
        if wheel_amount < 0:
            wheel_amount = wheel_amount & 0xFFFFFFFF
        wparam = wheel_amount << 16
        # MK_LBUTTON 같은 modifier flag 는 lower word — 0 으로 둠

        lparam = _makelparam(abs_x, abs_y)

        # WindowFromPoint 로 실제 자식 윈도우 타겟팅
        import ctypes
        import ctypes.wintypes as wintypes
        user32 = ctypes.windll.user32
        pt = wintypes.POINT(abs_x, abs_y)
        target = user32.WindowFromPoint(pt)
        if not target:
            target = hwnd

        # PostMessage WM_MOUSEWHEEL — 부호 있는 wheel delta
        wheel_signed = (ticks * WHEEL_DELTA) & 0xFFFF
        wparam_packed = (wheel_signed << 16) | 0
        win32api.PostMessage(target, win32con.WM_MOUSEWHEEL,
                             wparam_packed, lparam)
        time.sleep(0.15)

    def scroll_friends_list(self, ticks: int = -3):
        """
        친구 목록 영역 중앙에 스크롤 이벤트 전송
        스크롤 가능 영역 = 메인 창 중앙
        """
        rect = self.get_window_rect()
        if not rect:
            return
        cx = rect["x"] + rect["width"] // 2
        cy = rect["y"] + rect["height"] // 2
        self.scroll_at(cx, cy, ticks=ticks)

    # ── Phase 1: 키보드 네비게이션 기반 단일 사이클 자동화 ──

    # 행 높이 (검증됨: 카톡 친구탭 56px)
    ROW_HEIGHT = 56

    def _press_arrow_down(self):
        """↓ 키 시스템 전역 이벤트 (포커스된 컨트롤로 전달)
        검증: PostMessage 는 자식 컨트롤에 도달 못 함 → keybd_event 사용
        """
        import ctypes
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(win32con.VK_DOWN, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(win32con.VK_DOWN, 0, KEYEVENTF_KEYUP, 0)

    def _diff_excluding_ads(self, img1, img2):
        """광고 영역 제외 후 이미지 diff bbox. 광고만 변하면 None 반환."""
        from PIL import ImageChops
        diff = ImageChops.difference(img1, img2)
        bbox = diff.getbbox()
        if bbox is None:
            return None

        ad_y = int(img1.height * self.AD_AREA_RATIO)
        x1, y1, x2, y2 = bbox

        # 광고 영역에서만 변경 → no-change
        if y1 >= ad_y:
            return None

        # 광고 영역 잘라내기
        if y2 > ad_y:
            y2 = ad_y

        return (x1, y1, x2, y2)

    def _ocr_single_line(self, image) -> str:
        """행 ROI OCR — PaddleOCR 우선 (95%+ 정확도), 폴백 Windows OCR → Tesseract.

        PaddleOCR 의 강점:
          - 텍스트를 박스별 분리 인식 → 가장 위쪽(y 작은) 박스 = 이름
          - 직함/별명이 같이 나와도 첫 박스만 가져오면 이름만
          - 한국어 모델 학습돼서 작은 글자에도 95%+ 정확

        실패 시 폴백:
          - Windows.Media.Ocr (~70% 정확)
          - Tesseract 다중 PSM (~50% 정확)
        """
        if image.size[0] < 10 or image.size[1] < 10:
            return ""

        # 1) PaddleOCR 우선
        paddle = _get_paddle_ocr()
        if paddle is not None:
            try:
                text = self._paddle_ocr_row(paddle, image)
                if text and re.search(r"[가-힣]", text):
                    _diag(f"engine=paddle text={text!r}")
                    return text
            except Exception as e:
                _diag(f"paddle_ocr_row 예외 → 폴백: {e!r}")

        # 2) 폴백: Windows OCR + Tesseract — 행 상단 + 5x 확대
        w, h = image.size
        name_region = image.crop((0, 0, w, max(int(h * 0.8), 28)))
        big = name_region.resize(
            (name_region.width * 5, name_region.height * 5),
            __import__("PIL.Image", fromlist=["LANCZOS"]).LANCZOS,
        )

        # Windows OCR
        if _WIN_OCR_AVAILABLE:
            try:
                text = self._win_ocr(big)
                if text and re.search(r"[가-힣]", text):
                    cleaned = re.sub(r"\s+", " ", text).strip()
                    _diag(f"engine=winocr text={cleaned!r}")
                    return cleaned
            except Exception:
                pass

        # Tesseract 최종 폴백
        try:
            import pytesseract
        except ImportError:
            return ""

        preprocessed = self.ocr.preprocess_image(big)
        candidates = []
        for psm in [6, 7, 11]:
            try:
                text = pytesseract.image_to_string(
                    preprocessed,
                    lang=self.ocr.language,
                    config=self.ocr._get_config(psm),
                ).strip()
                text = re.sub(r"\s+", " ", text)
                candidates.append(text)
            except Exception:
                continue

        if not candidates:
            return ""

        def hangul_count(s: str) -> int:
            return len(re.findall(r"[가-힣]", s))

        best = max(candidates, key=lambda t: (hangul_count(t), len(t)))
        _diag(f"engine=tesseract text={best!r}")
        return best

    def _paddle_ocr_row(self, paddle, image) -> str:
        """PaddleOCR 입력 전처리 + 5배 확대 → 인식률 대폭 향상.

        파이프라인:
          1) 5배 확대 (Lanczos)
          2) 회색조 변환 (한글은 흑백이 더 정확)
          3) 대비 1.5배 강화 (글자 윤곽 선명)
          4) UnsharpMask (선명도 강화 — 안티앨리어싱 흐림 보정)
          5) RGB 복원 → PaddleOCR
        """
        import numpy as np
        from PIL import Image as _PILImage, ImageEnhance, ImageFilter

        # 1) 5배 확대
        big = image.resize(
            (image.width * 5, image.height * 5),
            _PILImage.LANCZOS,
        )

        # 2~4) 전처리 — 회색조 → 대비 → 샤프닝
        gray = big.convert("L")
        contrasted = ImageEnhance.Contrast(gray).enhance(1.5)
        sharpened = contrasted.filter(
            ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)
        )

        # 5) RGB 복원 (PaddleOCR 3채널 기대)
        rgb = sharpened.convert("RGB")
        arr = np.array(rgb)

        result = paddle.ocr(arr, cls=False)
        if not result or not result[0]:
            return ""

        items = []
        for entry in result[0]:
            box, (text, conf) = entry
            if not text or conf < 0.5:
                continue
            ys = [pt[1] for pt in box]
            xs = [pt[0] for pt in box]
            items.append({
                "text": text.strip(),
                "conf": conf,
                "y": min(ys),
                "x": min(xs),
            })

        if not items:
            return ""

        # y(위→아래), x(좌→우) 순 정렬
        items.sort(key=lambda i: (i["y"], i["x"]))
        joined = " ".join(it["text"] for it in items)
        return joined.strip()

    # 모듈 레벨 이벤트 루프 캐싱 (winrt 호출은 async)
    _win_ocr_loop = None

    def _win_ocr(self, pil_image) -> str:
        """Windows.Media.Ocr 동기 래퍼 (async API → sync)"""
        if not _WIN_OCR_AVAILABLE:
            return ""

        # PIL → PNG bytes
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        data = buf.getvalue()

        async def recognize():
            stream = _wstreams.InMemoryRandomAccessStream()
            writer = _wstreams.DataWriter(stream)
            writer.write_bytes(data)
            await writer.store_async()
            stream.seek(0)

            decoder = await _wimg.BitmapDecoder.create_async(stream)
            bitmap = await decoder.get_software_bitmap_async()

            engine = _wocr.OcrEngine.try_create_from_language(
                _wglob.Language("ko")
            )
            if engine is None:
                return ""

            result = await engine.recognize_async(bitmap)
            return result.text or ""

        # 이벤트 루프 재사용 (스레드별)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("loop closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(recognize())

    def _classify_row_text(self, text: str) -> tuple:
        """
        OCR된 행 텍스트 → (section, day, name)

        section: "birthday" | "channel" | "friend" | "header" | "unknown"
        day:     "today" | "other" | None
        name:    추출된 이름 (또는 원본 텍스트)
        """
        if not text:
            return ("unknown", None, "")

        # 생일 시점 라벨 — 키워드 1개라도 매치 시 birthday 로 분류 (관대).
        # 친구 섹션 진입 후엔 어차피 분류 결과 무시되므로 false-positive 안전함.
        # find_friend_section_start 단계에서만 의미 있고, 거기선 false-positive 가
        # false-negative 보다 훨씬 안전 (생일자 행을 친구로 저장하면 안 됨).
        def _extract_korean_name(s: str) -> str:
            tokens = re.findall(r"[가-힣]+", s)
            for t in tokens:
                if 2 <= len(t) <= 10:
                    return t
            return tokens[0] if tokens else ""

        for kw in self.DAY_TODAY:
            if kw in text:
                cleaned = re.sub(r"오늘\s*\d*월?\s*\d*일?", "", text)
                name = _extract_korean_name(cleaned)
                return ("birthday", "today", name)
        # ★ 어제/내일 구분 — _sync_birthday_to_contacts 가 yesterday/tomorrow
        #   라벨로 MM-DD 산출하므로 합쳐서 "other" 로 묶으면 DB 저장이 안 됨.
        for kw in self.DAY_YESTERDAY:
            if kw in text:
                cleaned = re.sub(r"(어제|그제)\s*\d*월?\s*\d*일?", "", text)
                name = _extract_korean_name(cleaned)
                return ("birthday", "yesterday", name)
        for kw in self.DAY_TOMORROW:
            if kw in text:
                cleaned = re.sub(r"(내일|모레)\s*\d*월?\s*\d*일?", "", text)
                name = _extract_korean_name(cleaned)
                return ("birthday", "tomorrow", name)

        # 채널 헤더 또는 채널 행
        for kw in self.SECTION_CHANNEL:
            if kw in text:
                return ("channel", None, text)

        # "친구 N" / "진구 N" 헤더 (헤더 본인은 보통 ↓ 키로 안 잡히지만 안전망)
        if re.search(r"친\s*구\s*\d+|진\s*구\s*\d+", text):
            return ("header", None, text)

        # 생일 안내 텍스트 ("친구의 생일을 확인해 보세요")
        if "확인" in text or "보세요" in text:
            return ("header", None, text)

        # 그 외 — 한글 토큰 검사
        if re.search(r"[가-힣]", text):
            korean_tokens = re.findall(r"[가-힣]+", text)
            if not korean_tokens:
                return ("unknown", None, text)

            # 휴리스틱: "첫 번째 2~10자 한글 토큰" = 이름
            primary = None
            for tok in korean_tokens:
                if 2 <= len(tok) <= 10:
                    primary = tok
                    break

            # 2자 이상 토큰이 하나도 없으면 unknown — 1자만 잡히는 건
            # OCR 가 거의 실패한 케이스. 노이즈로 저장하지 않음.
            if primary is None:
                return ("unknown", None, "")

            # 성씨 사전 보정/가나다 보정 모두 제거.
            # 이유: 잘못된 변환 한 번이 후속 행에 전파되어 더 큰 오류 발생.
            # Paddle 결과를 그대로 신뢰. 사용자 검토는 사후 단계에서.

            return ("friend", None, primary)

        return ("unknown", None, text)

    # 같은 줄 판정 임계 (paddle 5x 스케일 좌표 기준). 이름줄과 상태메시지줄
    # 간격은 검증상 최소 ~85px → 50 이면 안전히 분리.
    _NAME_LINE_TOL = 50

    def _ocr_row_text_and_name(self, image) -> tuple:
        """행 OCR → (row_text, display_name).

        - row_text: 박스 전체를 합친 문자열 (섹션/생일 분류용 — 기존과 동일).
        - display_name: paddle 박스 중 '최상단 줄'을 x(좌→우) 순으로 합친 표시이름.
          상태메시지/생일날짜(아랫줄)는 제외, 라벨·복합이름은 그대로 보존(verbatim).
        paddle 실패 시 (row_text=_ocr_single_line 폴백, display_name="").
        """
        try:
            from core.paddle_ocr_helper import recognize_korean_text
            res = recognize_korean_text(image)
            boxes = res.get("boxes") or []
            if res.get("engine") == "paddle" and boxes:
                top_y = min(b["y"] for b in boxes)
                line = [b for b in boxes
                        if b["y"] - top_y <= self._NAME_LINE_TOL]
                line.sort(key=lambda b: b["x"])
                display_name = " ".join(b["text"] for b in line).strip()
                return res.get("text", ""), display_name
        except Exception:
            pass
        # 폴백: paddle 미작동 행 → 기존 단일라인 OCR, 표시이름은 분류기에 위임
        return self._ocr_single_line(image), ""

    def navigate_step(self, prev_image=None,
                       wait_after: float = 0.15) -> dict:
        """
        ↓ 1회 → 새 선택 행 식별 + OCR.

        Args:
            prev_image: 이전 스크린샷. None 이면 직전 캡처.
            wait_after: ↓ 후 대기 (UI 반영 시간)

        Returns:
            {
                "moved": bool,           # False = 광고 외 변화 없음 (끝 가능성)
                "prev_image": Image,
                "cur_image": Image,
                "row_image": Image|None,
                "row_text": str,
                "name": str,             # 정제된 이름
                "section": str,          # birthday/channel/friend/header/unknown
                "day": str|None,         # today/other/None
                "is_today_birthday": bool,
            }
        """
        rect = self.get_window_rect()
        if not rect:
            return self._empty_step_result(prev_image)

        if prev_image is None:
            prev_image = self.capture_window()

        # ↓ 키 + 대기
        self._press_arrow_down()
        time.sleep(wait_after)

        cur_image = self.capture_window()

        # diff (광고 제외)
        body_bbox = self._diff_excluding_ads(prev_image, cur_image)
        if body_bbox is None:
            return {
                "moved": False,
                "prev_image": prev_image,
                "cur_image": cur_image,
                "row_image": None,
                "row_text": "",
                "name": "",
                "section": "unknown",
                "day": None,
                "is_today_birthday": False,
            }

        # 새 선택 행 = diff bbox 의 아래쪽 1행 (ROW_HEIGHT)
        x1, y1, x2, y2 = body_bbox
        row_y1 = max(0, y2 - self.ROW_HEIGHT)
        row_y2 = y2

        # ROI x 좁히기: 프로필 이미지(좌측 ~25%) + 우측 버튼(우측 ~25%) 제외
        # 이름/날짜는 가운데 영역에 위치
        full_w = cur_image.width
        roi_x1 = int(full_w * 0.20)
        roi_x2 = int(full_w * 0.78)
        # diff bbox 도 고려해서 더 좁은 쪽 채택
        crop_x1 = max(x1, roi_x1)
        crop_x2 = min(x2, roi_x2)
        if crop_x2 <= crop_x1:
            crop_x1, crop_x2 = roi_x1, roi_x2

        row_img = cur_image.crop((crop_x1, row_y1, crop_x2, row_y2))

        # OCR — paddle 박스 기반: row_text(전체, 분류용) + display_name(상단 줄=표시이름)
        row_text, display_name = self._ocr_row_text_and_name(row_img)
        section, day, name = self._classify_row_text(row_text)
        # ★ 친구·생일 행이면 화면에 보이는 표시이름(상단 줄 전체)을 그대로 사용.
        #   라벨(고객 등)·복합이름 보존, 상태메시지/생일날짜(아랫줄)는 제외.
        #   → 친구 저장 이름과 생일자 이름이 동일해져 생일 자동저장 매칭이 됨.
        if section in ("friend", "birthday") and display_name:
            name = display_name

        return {
            "moved": True,
            "prev_image": prev_image,
            "cur_image": cur_image,
            "row_image": row_img,
            "row_text": row_text,
            "name": name,
            "section": section,
            "day": day,
            "is_today_birthday": section == "birthday" and day == "today",
        }

    def _empty_step_result(self, prev_image):
        return {
            "moved": False,
            "prev_image": prev_image,
            "cur_image": prev_image,
            "row_image": None,
            "row_text": "",
            "name": "",
            "section": "unknown",
            "day": None,
            "is_today_birthday": False,
        }

    def reset_to_top(self) -> bool:
        """
        친구탭을 맨 위로 스크롤 (자동화 시작 전 호출).

        시도 순서:
          1) Home 키 (시스템 전역)
          2) Ctrl+Home (백업)
          3) 휠 위로 (백업의 백업)
        """
        import ctypes
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002

        self.win32.activate(self.win32.main_hwnd)
        time.sleep(0.4)

        # 1) Home
        user32.keybd_event(win32con.VK_HOME, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(win32con.VK_HOME, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.5)

        # 친구탭 첫 화면 확인
        hits = self.find_text_hits()
        if self.find_text(self.SECTION_BIRTHDAY, hits=hits) or \
           self.find_text(self.SECTION_UPDATED, hits=hits):
            return True

        # 2) Ctrl+Home
        user32.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(win32con.VK_HOME, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(win32con.VK_HOME, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)
        user32.keybd_event(win32con.VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.5)

        hits = self.find_text_hits()
        if self.find_text(self.SECTION_BIRTHDAY, hits=hits) or \
           self.find_text(self.SECTION_UPDATED, hits=hits):
            return True

        # 3) 휠 위로 강하게 (5번)
        rect = self.get_window_rect()
        if rect:
            cx = rect["x"] + rect["width"] // 2
            cy = rect["y"] + rect["height"] // 2
            for _ in range(5):
                self.scroll_at(cx, cy, ticks=10)  # 양수 = 위
                time.sleep(0.2)

        hits = self.find_text_hits()
        return bool(self.find_text(self.SECTION_BIRTHDAY, hits=hits) or
                    self.find_text(self.SECTION_UPDATED, hits=hits))

    def _ocr_row_at_y(self, y_abs: int, image=None) -> dict:
        """절대 y 좌표 위치의 행을 OCR + 분류.
        click_first_birthday 처럼 navigate_step 없이 이름이 필요한 경우 사용.
        """
        rect = self.get_window_rect()
        if not rect or not image:
            if image is None:
                image = self.capture_window()

        local_y = y_abs - rect["y"]
        row_y1 = max(0, local_y - self.ROW_HEIGHT // 2)
        row_y2 = min(image.height, local_y + self.ROW_HEIGHT // 2)

        full_w = image.width
        crop_x1 = int(full_w * 0.20)
        crop_x2 = int(full_w * 0.78)

        row_img = image.crop((crop_x1, row_y1, crop_x2, row_y2))
        text = self._ocr_single_line(row_img)
        section, day, name = self._classify_row_text(text)

        return {
            "row_text": text,
            "section": section,
            "day": day,
            "name": name,
        }

    # ── 카톡 시작 상태 감지 + 자동 정상화 ──

    # 검색창 식별 키워드 — 검색창에만 나타나는 "통합검색" 만 사용
    # ("이름 검색" 은 placeholder 라 OCR 에 안 잡히거나 다른 곳에서 잡힐 위험)
    SEARCH_OPEN_KEYWORDS = ["통합검색", "통 합 검 색"]

    # 채팅탭 식별 키워드 (헤더 위치)
    TAB_CHAT_KEYWORDS = ["채팅", "채 팅"]

    def detect_screen_state(self, hits=None) -> dict:
        """
        현재 카톡 화면 상태 감지 — PaddleOCR 우선 (정확도) + Tesseract 폴백.

        Returns:
            {
                "tab": "friends" | "chat" | "unknown",
                "search_open": bool,
                "ready_to_send": bool,
                "header_text": str,
                "engine": "paddle" | "tesseract",
            }
        """
        rect = self.get_window_rect()
        if not rect:
            return {
                "tab": "unknown", "search_open": False,
                "ready_to_send": False, "header_text": "",
                "engine": "none",
            }

        # 1) PaddleOCR 우선 — 상단 30% 영역만 (헤더 + 검색바)
        try:
            from core.paddle_ocr_helper import recognize_korean_text
            img = self.capture_window()
            top_h = int(img.height * 0.30)
            top_region = img.crop((0, 0, img.width, top_h))
            res = recognize_korean_text(top_region)
            full_text = res["text"]
            engine = res["engine"]
        except Exception:
            full_text = ""
            engine = "none"

        # Paddle 결과로 판단
        if engine == "paddle" and full_text:
            text_clean = full_text.replace(" ", "")

            # 탭 감지
            tab = "unknown"
            header_text = ""
            if "친구" in text_clean or "진구" in text_clean:
                tab = "friends"
                header_text = "친구"
            elif any(kw.replace(" ", "") in text_clean
                     for kw in self.TAB_CHAT_KEYWORDS):
                tab = "chat"
                header_text = "채팅"

            # 검색창 열림 — 강력 키워드
            search_open = (
                "통합검색" in text_clean or
                "이름검색" in text_clean
            )

            return {
                "tab": tab,
                "search_open": search_open,
                "ready_to_send": (tab == "friends" and not search_open),
                "header_text": header_text,
                "engine": "paddle",
            }

        # 2) Paddle 실패 → Tesseract 폴백 (기존 로직)
        if hits is None:
            hits = self.find_text_hits()

        top_y_threshold = rect["y"] + int(rect["height"] * 0.10)
        search_y_threshold = rect["y"] + int(rect["height"] * 0.25)

        tab = "unknown"
        header_text = ""
        for h in hits:
            if h.y > top_y_threshold:
                continue
            t = h.text.strip()
            if t in ("친구", "진구"):
                tab = "friends"
                header_text = t
                break
            for kw in self.TAB_CHAT_KEYWORDS:
                if kw in t:
                    tab = "chat"
                    header_text = t
                    break
            if tab != "unknown":
                break

        if tab == "unknown":
            for kws in (self.SECTION_UPDATED, self.SECTION_BIRTHDAY):
                if self.find_text(kws, hits=hits):
                    tab = "friends"
                    break

        search_open = False
        for h in hits:
            if h.y > search_y_threshold:
                continue
            t = h.text.strip()
            for kw in self.SEARCH_OPEN_KEYWORDS:
                if kw in t or t in kw:
                    search_open = True
                    break
            if search_open:
                break

        return {
            "tab": tab,
            "search_open": search_open,
            "ready_to_send": (tab == "friends" and not search_open),
            "header_text": header_text,
            "engine": "tesseract",
        }

    def _click_friends_tab_icon(self, friends_icon: dict = None) -> bool:
        """좌측 사이드바 사람 아이콘 클릭 → 친구탭 전환.

        Args:
            friends_icon: {"x": int, "y": int}. 호출자가 셋업 좌표 넘기면
                절대좌표 사용. None 이면 learned_positions.json 폴백 → 추정값.
        """
        # 1) 인자로 받은 좌표 (호출자가 KakaoSender.coords 에서 넘김)
        click_x = None
        click_y = None
        if (friends_icon and isinstance(friends_icon, dict)
                and "x" in friends_icon and "y" in friends_icon):
            click_x = friends_icon["x"]
            click_y = friends_icon["y"]

        # 2) 폴백: learned_positions.json 직접 로드
        if click_x is None:
            import json
            import os
            import sys
            here = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                "config/learned_positions.json",
                os.path.join(os.path.dirname(here), "config",
                              "learned_positions.json"),
            ]
            if getattr(sys, "frozen", False):
                meipass = getattr(sys, "_MEIPASS", None)
                if meipass:
                    candidates.append(os.path.join(
                        meipass, "config", "learned_positions.json"
                    ))
                exe_dir = os.path.dirname(sys.executable)
                candidates.append(os.path.join(
                    exe_dir, "_internal", "config", "learned_positions.json"
                ))
                candidates.append(os.path.join(
                    exe_dir, "config", "learned_positions.json"
                ))
            for path in candidates:
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            coords = json.load(f)
                        fi = coords.get("friends_tab_icon", {})
                        if "x" in fi and "y" in fi:
                            click_x = fi["x"]
                            click_y = fi["y"]
                            break
                    except Exception:
                        continue

        # 3) 최후 폴백: 창 좌표 + 추정 오프셋 (검증 안 됨, 셋업 권장)
        if click_x is None:
            rect = self.get_window_rect()
            if not rect:
                return False
            click_x = rect["x"] + 35
            click_y = rect["y"] + 50

        try:
            from core.kakao_win32 import _log as _w32_log
            _w32_log(f"_click_friends_tab_icon: ({click_x},{click_y})")
        except Exception:
            pass

        # ★ 카톡 main 활성화 후 클릭 — 백그라운드/다른 창 포그라운드면 stealth
        #   클릭이 엉뚱한 창(예: 브라우저, TalkPC-Pro UI)에 가서 탭 전환 실패.
        #   스케줄러 자동발송 시 이 경로 잡혀서 친구탭 못 찍던 문제 원인.
        # 클릭 + 검증(친구탭으로 실제 전환됐는지) + 1회 재시도.
        for attempt in range(2):
            self.win32.activate(self.win32.main_hwnd)
            time.sleep(0.4)
            old_mode = self.win32.click_mode
            self.win32.click_mode = self.win32.MODE_STEALTH
            try:
                self.win32.click(click_x, click_y)
                time.sleep(0.8)
            finally:
                self.win32.click_mode = old_mode

            # 친구탭 활성화 검증 — 상단 25% 에 "친구" 텍스트 있고 "채팅" 없으면 OK
            try:
                hits = self.find_text_hits()
                if self.is_friends_tab_active(hits=hits):
                    try:
                        from core.kakao_win32 import _log as _w32_log
                        _w32_log(f"_click_friends_tab_icon: 검증 OK (attempt={attempt+1})")
                    except Exception:
                        pass
                    return True
            except Exception:
                pass

            try:
                from core.kakao_win32 import _log as _w32_log
                _w32_log(
                    f"_click_friends_tab_icon: attempt={attempt+1} 친구탭 미활성 — "
                    f"재시도 예정" if attempt == 0 else f"_click_friends_tab_icon: 재시도 후에도 친구탭 미활성"
                )
            except Exception:
                pass
        return False

    def _close_search_box(self) -> bool:
        """검색창 닫기 — 검색 아이콘(돋보기)을 한 번 누르면 토글로 닫힘.

        카톡 PC 의 검색 아이콘은 토글 동작:
          - 검색창 닫혀있을 때 클릭 → 열림
          - 검색창 열려있을 때 클릭 → 닫힘

        ★ X 버튼 좌표 추정 불필요. learned_positions.json 의 search_icon
           좌표를 그대로 사용 (이미 사용자가 셋업해서 정확).
        """
        import json
        import os
        import sys

        # 검색 아이콘 좌표 로드 — 빌드 환경 호환 위해 절대경로 폴백 추가
        search_icon = None
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            "config/learned_positions.json",
            "config\\learned_positions.json",
            os.path.join(here, "..", "config", "learned_positions.json"),
            os.path.join(os.path.dirname(here), "config",
                          "learned_positions.json"),
        ]
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(os.path.join(
                    meipass, "config", "learned_positions.json"
                ))
            exe_dir = os.path.dirname(sys.executable)
            candidates.append(os.path.join(
                exe_dir, "_internal", "config", "learned_positions.json"
            ))
            candidates.append(os.path.join(
                exe_dir, "config", "learned_positions.json"
            ))
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        coords = json.load(f)
                    si = coords.get("search_icon", {})
                    if "x" in si and "y" in si:
                        search_icon = si
                        break
                except Exception:
                    continue

        if not search_icon:
            try:
                from core.kakao_win32 import _log as _w32_log
                _w32_log("_close_search_box: search_icon 좌표 없음, 스킵")
            except Exception:
                pass
            return False

        # 검색 아이콘 클릭 → 검색창 닫힘 (토글)
        # stealth 모드 (실제 마우스 이벤트 — 토글 보장)
        try:
            from core.kakao_win32 import _log as _w32_log
            _w32_log(
                f"_close_search_box: 검색아이콘 토글클릭 "
                f"({search_icon['x']},{search_icon['y']})"
            )
        except Exception:
            pass

        old_mode = self.win32.click_mode
        self.win32.click_mode = self.win32.MODE_STEALTH
        try:
            self.win32.click(search_icon["x"], search_icon["y"])
            time.sleep(0.6)
        finally:
            self.win32.click_mode = old_mode

        # 닫혔는지 재확인
        state = self.detect_screen_state()
        return not state["search_open"]

    def ensure_ready_state(
        self, max_attempts: int = 3,
        friends_icon: dict = None, search_icon: dict = None,
    ) -> dict:
        """발송 시작 정상화 — 친구 체크 일절 없음.

        흐름:
          1) 무조건 사람 아이콘 클릭 (친구탭이든 채팅탭이든 친구탭으로)
          2) 검색바 ROI 만 OCR → "통합검색"/"이름검색" 잡히면 search_icon 1회 클릭
          3) 끝. (친구/채팅 detect_screen_state 호출 X)
        """
        actions = []

        # 1) 사람 아이콘 무조건 클릭
        try:
            self._click_friends_tab_icon(friends_icon=friends_icon)
            actions.append("사람 아이콘 클릭")
            time.sleep(0.6)
        except Exception as e:
            actions.append(f"사람 아이콘 클릭 실패: {e}")

        # 2) search_icon 좌표 확보 (ROI 계산 + 클릭 둘 다 사용)
        # 인자 우선, 없으면 learned_positions.json 폴백
        si = (search_icon
              if (search_icon and "x" in search_icon
                  and "y" in search_icon)
              else None)
        if si is None:
            import json as _json
            import os as _os
            import sys as _sys
            _here = _os.path.dirname(_os.path.abspath(__file__))
            _candidates = [
                "config/learned_positions.json",
                _os.path.join(_os.path.dirname(_here), "config",
                               "learned_positions.json"),
            ]
            if getattr(_sys, "frozen", False):
                _exe_dir = _os.path.dirname(_sys.executable)
                _candidates += [
                    _os.path.join(_exe_dir, "_internal", "config",
                                   "learned_positions.json"),
                    _os.path.join(_exe_dir, "config",
                                   "learned_positions.json"),
                ]
            for _p in _candidates:
                if _os.path.exists(_p):
                    with open(_p, "r", encoding="utf-8") as _f:
                        _c = _json.load(_f)
                    _s = _c.get("search_icon", {})
                    if "x" in _s and "y" in _s:
                        si = _s
                        break

        # 3) 검색창 열림 검사 — search_icon.y 기준 동적 ROI
        # 이전엔 img.height * 0.05~0.14 (퍼센트) 였으나 카톡 창이 작으면
        # 통합검색 글자 (search_input ≈ search_icon.y + 52px) 가 ROI 바깥
        # 으로 빠져 search_open 검출 실패 → 검색창 열려있는데도 안 닫힘.
        # ※ search_icon 좌표는 모니터 절대 좌표, capture_window 이미지는
        #   카톡 창 상대 좌표 → rect.y 만큼 빼서 변환 필요.
        search_open = False
        try:
            from core.paddle_ocr_helper import recognize_korean_text
            img = self.capture_window()
            rect = self.get_window_rect() or {"x": 0, "y": 0}
            if si and "y" in si:
                # 모니터 절대 → 카톡 창 상대 좌표 변환
                si_img_y = si["y"] - rect.get("y", 0)
                # 돋보기 위 20px ~ 아래 80px (통합검색 글자 영역 확실히 포함)
                sb_top = max(0, si_img_y - 20)
                sb_bot = min(img.height, si_img_y + 80)
            else:
                # 폴백 — search_icon 좌표 못 구하면 detect_screen_state 와 동일 30%
                sb_top = 0
                sb_bot = int(img.height * 0.30)
            sb_region = img.crop((0, sb_top, img.width, sb_bot))
            res = recognize_korean_text(sb_region)
            text = (res.get("text") or "").replace(" ", "")
            if "통합검색" in text or "이름검색" in text:
                search_open = True
        except Exception as e:
            actions.append(f"검색창 ROI OCR 실패 (계속): {e}")

        # 4) 검색창 열려있으면 search_icon 1회 클릭 (직접 — _close_search_box 미호출)
        if search_open:
            try:
                if si:
                    try:
                        from core.kakao_win32 import _log as _w32_log
                        _w32_log(
                            f"ensure_ready_state: 검색창 열림 → "
                            f"search_icon 클릭 ({si['x']},{si['y']})"
                        )
                    except Exception:
                        pass
                    old_mode = self.win32.click_mode
                    self.win32.click_mode = self.win32.MODE_STEALTH
                    try:
                        self.win32.click(si["x"], si["y"])
                        time.sleep(0.6)
                    finally:
                        self.win32.click_mode = old_mode
                    actions.append("검색창 닫음 (search_icon 1회)")
            except Exception as e:
                actions.append(f"search_icon 클릭 실패: {e}")

        return {
            "ok": True,
            "actions": actions,
            "final_state": {"search_open": search_open},
        }

    def is_friends_tab_active(self, hits=None) -> bool:
        """
        현재 카톡 화면이 친구탭인지 확인.

        친구탭 시그니처:
          - "친구" 텍스트가 화면 상단(y < 창 높이의 25%)에 단독으로 잡힘
          - 또는 "업데이트한 친구" 또는 "생일인 친구" 헤더 존재

        채팅탭이면 "채팅" 텍스트가 헤더에 있어 구별됨.
        """
        if hits is None:
            hits = self.find_text_hits()

        rect = self.get_window_rect()
        if not rect:
            return False
        top_y_threshold = rect["y"] + int(rect["height"] * 0.25)

        # 채팅탭 시그니처 — 상단에 "채팅" 텍스트 있으면 친구탭 아님
        for h in hits:
            if h.y <= top_y_threshold and "채팅" in h.text:
                return False

        # 친구탭 시그니처
        for h in hits:
            if h.y <= top_y_threshold and h.text.strip() in ("친구", "진구"):
                return True

        # 보강 — 업데이트한/생일인 헤더가 있으면 친구탭 확실
        for kws in (self.SECTION_UPDATED, self.SECTION_BIRTHDAY):
            if self.find_text(kws, hits=hits):
                return True

        return False

    def click_first_birthday(self) -> dict:
        """
        첫 생일자 행 찾기 (네비게이션 시작점).
        오늘 생일자 우선, 없으면 어제/내일 생일자라도 OK (시작점만 필요).

        v0.1.11: 친구 수집과 동일한 ↓ 키 방식. 친구탭 맨 위로 reset → ↓ 키
        반복하며 navigate_step 으로 각 행 OCR → section 이 "birthday" 면 즉시
        성공, "friend" 만나면 생일 섹션이 없는 계정 → 빠른 종료.

        장점:
          - 새로운친구/업데이트한친구 길이에 상관없이 한 행씩 정확히 탐색.
          - 헤더("생일인 친구 N")가 viewport 밖이어도 OCR 부정확 영향 없음.
          - selection 이 자연스럽게 첫 생일자에 위치 → send_birthday_messages
            의 ↓ 루프가 그대로 이어짐 (별도 클릭 불필요).

        Returns:
            {
                "ok": bool,
                "reason": str,    # 실패 사유 (UI 표시용)
                "row": dict|None, # name/day/row_text/section
            }
        """
        self.win32.activate(self.win32.main_hwnd)
        time.sleep(0.5)

        hits = self.find_text_hits()
        if not self.is_friends_tab_active(hits=hits):
            _diag("click_first_birthday: 친구탭 비활성")
            return {"ok": False, "reason": "카톡 친구탭이 활성화돼 있지 않습니다.", "row": None}

        # 맨 위로 — viewport 가 처음 위치에서 시작
        self.reset_to_top()
        time.sleep(0.4)

        # ★ ↓ 키 input 이 친구탭 리스트로 가게 하려면 초기 selection 이 필요.
        #   없으면 ↓ 가 무시되거나 다른 위젯으로 감 → 첫 navigate_step 이 moved=False.
        #   친구탭 최상단(본인 프로필 행 위치)에 stealth-click 으로 selection 박기.
        rect = self.get_window_rect()
        if rect:
            seed_x = rect["x"] + rect["width"] // 2
            # 창 높이의 18% 지점 ≈ 본인 프로필 행 중앙 (탭헤더/검색바 아래 첫 행)
            seed_y = rect["y"] + int(rect["height"] * 0.18)
            old_mode = self.win32.click_mode
            self.win32.click_mode = self.win32.MODE_STEALTH
            try:
                self.win32.click(seed_x, seed_y)
                time.sleep(0.6)
            finally:
                self.win32.click_mode = old_mode
            _diag(f"click_first_birthday: seed click ({seed_x},{seed_y}) — 본인 프로필 행")

        # ↓ 키 반복 — 친구 수집과 동일 패턴. 생일 섹션은 보통 상단(프로필 직후).
        # MAX_STEPS=15: 프로필 + 채널 + 새로운/업데이트친구 합쳐 ~10 + 마진.
        # 15 step 안에 생일 안 잡히면 사실상 없는 거.
        # MAX_CONSECUTIVE_FRIEND=5: 친구 섹션 행 5번 연속 = 생일 섹션 지나친 거.
        #   더 빠른 종료(쓸데없이 친구목록 끝없이 ↓ 헤매기 방지).
        MAX_STEPS = 15
        MAX_CONSECUTIVE_NO_MOVE = 3
        MAX_CONSECUTIVE_FRIEND = 5
        friend_streak = 0
        no_move_streak = 0
        prev_image = self.capture_window()
        passed_sections = []

        for step in range(MAX_STEPS):
            # ★ 매 ↓ 전 카톡 main 재활성. 스케줄러 자동발송 시 TalkPC-Pro UI
            #   복귀로 포그라운드 가로채면 ↓ 키 입력이 묻혀버림.
            self.win32.activate(self.win32.main_hwnd)
            time.sleep(0.2)
            result = self.navigate_step(prev_image=prev_image)
            prev_image = result["cur_image"]

            if not result["moved"]:
                no_move_streak += 1
                _diag(f"click_first_birthday: step {step+1} moved=False (streak={no_move_streak})")
                # 추가 안정화 — main 재활성 + 더 길게 대기 후 재시도
                if no_move_streak < MAX_CONSECUTIVE_NO_MOVE:
                    self.win32.activate(self.win32.main_hwnd)
                    time.sleep(0.6)
                    prev_image = self.capture_window()
                if no_move_streak >= MAX_CONSECUTIVE_NO_MOVE:
                    _diag(f"click_first_birthday: ↓ {MAX_CONSECUTIVE_NO_MOVE}회 연속 안 움직임 → 종료 (최후 섹션={passed_sections[-3:]})")
                    return {"ok": False,
                            "reason": "친구 목록 끝까지 갔지만 생일자를 못 찾았습니다.",
                            "row": None}
                continue
            no_move_streak = 0

            section = result["section"]
            name = result["name"]
            day = result["day"]
            _diag(f"click_first_birthday: step {step+1} section={section} day={day} name={name!r}")

            if section == "birthday":
                # 첫 생일자 찾음 — selection 이 이미 이 행에 있음
                return {
                    "ok": True,
                    "reason": "",
                    "row": {
                        "name": name or "(첫 생일자)",
                        "day": day,
                        "row_text": result["row_text"],
                        "section": "birthday",
                        "is_today_birthday": result.get("is_today_birthday", False),
                    },
                }

            # ★ section == "friend" 여도 종료하지 않음!
            #   본인 프로필 행(예: "김진균 충북교육감")이 friend 로 분류됨.
            #   업데이트한 친구들도 이름만 있어 friend 로 분류됨.
            #   → 생일 섹션은 이들 뒤에 있으므로 계속 ↓ 진행.
            #   종료는 (1) birthday 발견, (2) moved=False 3연속, (3) MAX_STEPS 초과 만.
            passed_sections.append(section)

        _diag(f"click_first_birthday: 최대 step({MAX_STEPS}) 초과")
        return {"ok": False,
                "reason": f"생일자를 찾지 못했습니다 (최대 {MAX_STEPS}행 탐색 후).",
                "row": None}

    def _legacy_click_first_birthday_by_coords(self) -> dict:
        """레거시 좌표 클릭 방식 — 보존용(현재 미사용)."""
        self.win32.activate(self.win32.main_hwnd)
        time.sleep(0.5)

        img = self.capture_window()
        hits = self.find_text_hits(image=img)

        if not self.is_friends_tab_active(hits=hits):
            return {"ok": False, "reason": "카톡 친구탭이 활성화돼 있지 않습니다.", "row": None}

        N = self.get_birthday_count(hits=hits)
        if not N:
            return {"ok": False, "reason": "생일인 친구 섹션을 찾을 수 없습니다.", "row": None}

        rows = self.find_birthday_rows(expected_count=N, hits=hits)
        if not rows:
            return {"ok": False, "reason": "생일자 행 좌표를 추출하지 못했습니다.", "row": None}

        # 오늘 생일자가 있으면 그것, 없으면 첫 행 (시작점만 필요)
        today_rows = [r for r in rows if r["day"] == "today"]
        target = today_rows[0] if today_rows else rows[0]

        # 핵심: PostMessage 클릭은 호버만 발생, selection 변경 안 됨.
        # ↓ 키 시작점이 잘못된 selection 이면 발송이 다른 사람한테 갈 수 있어 위험.
        # stealth 모드(실제 마우스 이벤트)로 일시 전환해서 selection 강제 변경.
        old_mode = self.win32.click_mode
        self.win32.click_mode = self.win32.MODE_STEALTH
        try:
            self.win32.click(target["click_x"], target["click_y"])
            time.sleep(0.7)
        finally:
            self.win32.click_mode = old_mode

        # 클릭한 행 이름/섹션 OCR (선택된 행을 식별해서 후속 발송 시 사용)
        ocr_info = self._ocr_row_at_y(target["click_y"])
        target["name"] = ocr_info["name"]
        target["row_text"] = ocr_info["row_text"]
        target["section"] = ocr_info["section"]
        # day 는 이미 find_birthday_rows 가 분류한 값 사용 (더 정확 — 행 주변 OCR 통합)

        return {"ok": True, "reason": "", "row": target}

    def _click_first_friend_directly(self) -> bool:
        """생일자 섹션이 없을 때 — 친구 섹션 첫 행을 직접 찾아 클릭.

        전략:
          - "친구 N" 헤더 위치 찾기 (또는 "업데이트한 친구" / "채널" 헤더 끝 위치)
          - 헤더 다음 행 (≈헤더_y + ROW_HEIGHT) 좌표 클릭
          - stealth 모드로 click → selection 확립
        """
        self.win32.activate(self.win32.main_hwnd)
        time.sleep(0.4)

        img = self.capture_window()
        hits = self.find_text_hits(image=img)
        rect = self.get_window_rect()
        if not rect:
            return False

        # 마지막 알려진 헤더의 y (가장 아래 헤더 = 친구 헤더 직전)
        last_header_y = 0
        for kws in (self.SECTION_BIRTHDAY, self.SECTION_UPDATED, self.SECTION_CHANNEL):
            info = self.get_section_count(kws, hits=hits)
            if info and info.get("header_hit"):
                last_header_y = max(last_header_y, info["header_hit"].y)

        # 클릭 좌표 — 마지막 헤더보다 한 행 + 약간 아래 (안전 마진)
        # 또는 화면 중앙 (fallback)
        if last_header_y > 0:
            click_y = last_header_y + self.ROW_HEIGHT + 30
        else:
            # 헤더 하나도 못 찾음 → 화면 중앙 클릭
            click_y = rect["y"] + rect["height"] // 2
        click_x = rect["x"] + int(rect["width"] * 0.35)

        # stealth 모드 클릭 (selection 변경)
        old_mode = self.win32.click_mode
        self.win32.click_mode = self.win32.MODE_STEALTH
        try:
            self.win32.click(click_x, click_y)
            time.sleep(0.7)
        finally:
            self.win32.click_mode = old_mode

        return True

    def find_friend_section_start(self, max_steps: int = 50,
                                    prev_image=None) -> dict:
        """
        ↓ 반복하며 친구 섹션 (이름만 있는 행) 첫 도달까지.

        Args:
            max_steps: 최대 ↓ 횟수. 기본 50 (생일자 ~10명 + 채널 ~5명 안전 마진)

        Returns:
            {
                "reached": bool,
                "steps_taken": int,
                "last_step": dict,    # 친구 섹션 첫 행 step 결과
                "trail": list[dict],  # 거쳐온 모든 step 의 요약
            }
        """
        # 카톡 친구탭 구조: 생일인 친구 → (안내문) → 즐겨찾는 친구 → 채널 → 친구 N
        # ★ 섹션 헤더(즐겨찾는 친구/친구 N)는 ↓ 로 선택이 안 돼 OCR 에 안 잡힘.
        #   행 스트림에서 신뢰할 마커는 "보세요"(생일끝 안내문) 와 "채널"(즐겨찾기↔친구
        #   경계) 뿐. → 채널을 통과한 뒤 첫 이름부터 진짜 친구.
        #   채널이 없는 계정 대비: 안내문 만난 시점에 전체화면 OCR 로 "즐겨찾는 친구 N"
        #   수를 읽어 그만큼만 이름을 건너뜀(이중 안전장치).
        trail = []
        last_step = None
        seen_notice = False     # 생일섹션 끝 안내문("…확인해 보세요") 통과
        seen_channel = False    # "채널" 행 통과 (즐겨찾기/채널 → 친구 경계)
        fav_to_skip = None      # 즐겨찾는 친구 수 (안내문 시점 1회 측정)
        favs_skipped = 0
        NOTICE_KW = ("확인", "보세요", "친구의 생일")

        for i in range(max_steps):
            step = self.navigate_step(prev_image=prev_image)
            prev_image = step["cur_image"]
            last_step = step
            text = step["row_text"] or ""
            section = step["section"]

            trail.append({
                "step": i + 1,
                "section": section,
                "day": step["day"],
                "name": step["name"],
                "row_text": text[:40],
            })

            if not step["moved"]:
                return {
                    "reached": False,
                    "steps_taken": i + 1,
                    "last_step": step,
                    "trail": trail,
                }

            # 1) 생일 섹션 → 통과
            if section == "birthday":
                continue

            # 2) 생일섹션 끝 안내문 → 즐겨찾기 수 측정(전체화면 OCR)
            if any(k in text for k in NOTICE_KW):
                if not seen_notice:
                    seen_notice = True
                    try:
                        info = self.get_section_count(self.SECTION_FAVORITE)
                        fav_to_skip = info["count"] if info else None
                    except Exception:
                        fav_to_skip = None
                continue

            # 3) 채널 행 → 즐겨찾기·채널 경계 통과 표시
            if section == "channel" or "채널" in text:
                seen_channel = True
                continue

            # 4) 이름 행 → 진짜 친구인지 판정
            if section == "friend":
                # 채널을 지났으면 무조건 친구 (즐겨찾기·채널 모두 통과)
                if seen_channel:
                    return {"reached": True, "steps_taken": i + 1,
                            "last_step": step, "trail": trail}
                # 안내문 자체가 없는 계정(즐겨찾기 없음) → 첫 이름이 친구
                if not seen_notice:
                    return {"reached": True, "steps_taken": i + 1,
                            "last_step": step, "trail": trail}
                # 즐겨찾기 수를 못 읽었으면 더 못 거르므로 완전수집 우선(첫 이름=친구)
                if fav_to_skip is None:
                    return {"reached": True, "steps_taken": i + 1,
                            "last_step": step, "trail": trail}
                # 즐겨찾기 수만큼 건너뛴 뒤면 친구
                if favs_skipped >= fav_to_skip:
                    return {"reached": True, "steps_taken": i + 1,
                            "last_step": step, "trail": trail}
                # 아직 즐겨찾기 구간 → 건너뜀
                favs_skipped += 1
                continue

            # header / unknown → 통과
            continue

        return {
            "reached": False,
            "steps_taken": max_steps,
            "last_step": last_step,
            "trail": trail,
        }

    def _send_to_current_selection(self, text: str,
                                     image_path: str = None,
                                     post_open_delay: float = 1.0,
                                     post_send_delay: float = 0.8) -> bool:
        """
        현재 ↓ 키로 선택된 친구에게 메시지 발송.

        흐름: Enter (채팅 열기) → paste_text → [paste_image] → Enter (전송) → ESC

        Args:
            text: 변수 치환 완료된 본문
            image_path: 이미지 첨부 경로 (선택)

        Returns:
            True (성공) | False (예외 발생)
        """
        try:
            _diag(f"_send_to_current_selection: 시작 text='{text[:30]}...'")
            # 1) Enter(main_hwnd) → 채팅창 별도 윈도우로 열림 (신버전 카톡 PC)
            self.win32.press_enter(self.win32.main_hwnd)
            time.sleep(post_open_delay)

            # 2) ★ 새로 뜬 채팅창을 포그라운드에서 잡아 chat_hwnd 로 등록.
            #    이걸 안 잡으면 전송 Enter/Esc 가 main_hwnd 로 가서 메시지 미전송 +
            #    main 의 X 버튼 영역 활성화로 카톡 자체가 닫히는 사고(kakao_sender
            #    go_back 주석 참조). 감지 실패 시 main_hwnd fallback.
            chat_hwnd = self.win32.get_foreground_as_chat()
            if chat_hwnd:
                self.win32.activate(chat_hwnd)
                time.sleep(0.3)
                _diag(f"_send_to_current_selection: 1) Enter(채팅열기) chat_hwnd={chat_hwnd}")
            else:
                _diag(f"_send_to_current_selection: 1) Enter(채팅열기) chat_hwnd=감지실패(main fallback)")

            # 3) 텍스트 붙여넣기 (포그라운드=채팅창, Ctrl+V 가 입력창으로)
            self.win32.paste_text(text)
            time.sleep(0.4)
            _diag(f"_send_to_current_selection: 2) paste_text done")

            # 4) 이미지 (선택)
            if image_path:
                self.win32.paste_image(image_path)
                time.sleep(0.5)
                _diag(f"_send_to_current_selection: 3) paste_image done")

            # 5) Enter(chat_hwnd) → 전송. press_enter() 는 chat_hwnd or main_hwnd
            #    자동 fallback 이라 인자 생략 OK.
            self.win32.press_enter()
            time.sleep(post_send_delay)
            _diag(f"_send_to_current_selection: 4) Enter(전송) done")

            # 6) ESC(chat_hwnd) → 채팅창 닫기. main_hwnd 로 가면 메인이 영향받아
            #    카톡 자체가 이상해질 수 있어 chat 으로 명시.
            esc_hwnd = self.win32.chat_hwnd or self.win32.main_hwnd
            self.win32.press_escape(esc_hwnd)
            time.sleep(0.5)
            _diag(f"_send_to_current_selection: 5) ESC(채팅닫기, hwnd={esc_hwnd}) done")

            # 7) main 재활성화 + chat_hwnd 초기화 → 다음 ↓ navigate 준비
            self.win32.activate(self.win32.main_hwnd)
            time.sleep(0.3)
            self.win32.chat_hwnd = None
            _diag(f"_send_to_current_selection: 6) main 복귀 + chat_hwnd 초기화 — return True")

            return True
        except Exception as e:
            _diag(f"_send_to_current_selection: 예외 발생 → return False: {e!r}")
            return False

    # ── Phase 2: 메인 자동화 루프 ──

    def send_birthday_messages(self,
                                 template_content: str,
                                 image_path: str = None,
                                 dry_run: bool = True,
                                 daily_limit: int = 50,
                                 max_steps: int = 30,
                                 on_progress=None,
                                 pre_scanned_rows: list = None) -> dict:
        """
        오늘 생일자에게만 카톡 자동 메시지 발송.

        흐름:
            reset_to_top → click_first_birthday → 루프:
                navigate_step → 오늘 생일이면 발송, 아니면 스킵
                생일 섹션 벗어나면 (channel/friend/header) 종료

        Args:
            template_content: %이름% 등 변수 포함된 본문 템플릿
            image_path: 이미지 첨부 경로 (선택)
            dry_run: True 면 OCR/판단만, 실제 발송 X (기본값)
            daily_limit: 일일 발송 한도 (안전장치)
            max_steps: 생일 섹션 최대 ↓ 횟수
            on_progress: callback(step_dict, action, idx) — UI 진행률용

        Returns:
            {
                "ok": bool,
                "sent": int,
                "skipped": int,
                "errors": list[str],
                "dry_run": bool,
                "targets": list[dict],   # 처리된 행들 (이름, 액션)
                "reason": str,           # 실패 사유 (실패 시)
            }
        """
        from core.message_engine import MessageEngine

        result = {
            "ok": False, "sent": 0, "skipped": 0, "errors": [],
            "dry_run": dry_run, "targets": [], "reason": "",
        }

        msg_engine = MessageEngine()

        # ── 친구탭 자동 정상화 — 사용자가 카톡 다른 탭(채팅 등) 보고 있을 수
        #   있음. ensure_ready_state 가 friends_tab_icon 클릭 + 검색창 닫기로
        #   자동 복귀. sender 가 주입돼 있으면 그 coords 사용.
        _diag(f"send_birthday_messages: sender={self.sender is not None}, "
              f"dry_run={dry_run}")
        friends_icon = None
        search_icon = None
        if self.sender is not None and hasattr(self.sender, "coords"):
            friends_icon = self.sender.coords.get("friends_tab_icon")
            search_icon = self.sender.coords.get("search_icon")
            _diag(f"send_birthday_messages: friends_icon={friends_icon}, "
                  f"search_icon={search_icon}")
        try:
            ready = self.ensure_ready_state(
                friends_icon=friends_icon,
                search_icon=search_icon,
            )
            _diag(f"send_birthday_messages: ensure_ready_state ok={ready.get('ok')} "
                  f"actions={ready.get('actions')} final={ready.get('final_state')}")
        except Exception as e:
            _diag(f"send_birthday_messages: ensure_ready_state 예외(무시): {e!r}")

        # ── 발송 모드 분기 ──
        # 카톡은 ↓ 로 생일 섹션을 지나가면 다음 click_first_birthday 시점에
        # 생일/채널 섹션을 자동 숨김(collapse). → 미리 enumerate 후 재navigate
        # 는 실패. dry_run/실발송 모두 "첫 생일자 찾기" 만 반복하는 게 안전.
        if dry_run:
            # ── Dry-run: 전체 enumerate (preview 용) ──
            if pre_scanned_rows is not None:
                scan_rows = pre_scanned_rows
            else:
                scan = self._scan_birthday_section(max_steps)
                if not scan["ok"]:
                    result["reason"] = scan["reason"]
                    return result
                scan_rows = scan["rows"]

            today_rows = [r for r in scan_rows if r["day"] == "today"]
            other_rows = [r for r in scan_rows if r["day"] != "today"]
            result["scan_rows"] = scan_rows
            _diag(f"send_birthday_messages(dry): today={len(today_rows)} other={len(other_rows)}")

            for nth, target_row in enumerate(today_rows):
                target = {
                    "step": nth, "name": target_row["name"], "day": "today",
                    "row_text": target_row["row_text"][:60], "action": "pending",
                }
                self._process_birthday_target(
                    target, template_content, image_path,
                    True, msg_engine, result, on_progress, idx=nth,
                )
            for r in other_rows:
                result["targets"].append({
                    "name": r["name"], "day": r["day"], "row_text": r["row_text"],
                    "action": "skip_not_today",
                })
                result["skipped"] += 1

            result["ok"] = True
            return result

        # ── 실발송: 스캔으로 today 목록 확정 → N번 발송 → 끝. 수동 방식과 동일. ──
        scan = self._scan_birthday_section(max_steps)
        if not scan["ok"]:
            result["reason"] = scan["reason"]
            return result

        scan_rows = scan["rows"]
        today_rows = [r for r in scan_rows if r["day"] == "today"]
        other_rows = [r for r in scan_rows if r["day"] != "today"]
        result["scan_rows"] = scan_rows
        _diag(f"send_birthday_messages(send): scan 완료 — today={len(today_rows)} other={len(other_rows)}")

        # other(어제/내일) DB 동기화용 기록만
        for r in other_rows:
            result["targets"].append({
                "name": r["name"], "day": r["day"],
                "row_text": r["row_text"], "action": "skip_not_today",
            })
            result["skipped"] += 1

        # 중복 방지 로그 (수동/카톡OCR/JSON 3 경로 공통)
        sent_log = getattr(self.sender, "_birthday_sent_log", None) if self.sender else None

        # today 명단 — 정확히 N번 발송하고 종료. 끝없이 찾기 없음.
        for nth, target_row in enumerate(today_rows):
            if result["sent"] >= daily_limit:
                result["reason"] = f"일일 한도 {daily_limit} 도달 — 종료"
                break

            target = {
                "step": nth, "name": target_row["name"], "day": "today",
                "row_text": target_row["row_text"][:60], "action": "pending",
            }

            # ★ 같은 날 같은 사람한테 이미 발송됐으면 skip — 3 경로 공통 로그.
            if sent_log is not None and sent_log.is_sent_today(target["name"]):
                target["action"] = "skip_already_sent_today"
                result["targets"].append(target)
                result["skipped"] += 1
                _diag(f"send_birthday_messages(send): nth={nth} '{target['name']}' 오늘 이미 발송됨 — skip")
                continue

            # nth 번째 today 생일자에 selection 박기
            pos_ok = self._navigate_to_nth_today_birthday(nth)
            if not pos_ok:
                target["action"] = "error_navigate"
                result["errors"].append(f"{target['name']}: 재navigate 실패")
                result["targets"].append(target)
                _diag(f"send_birthday_messages(send): nth={nth} '{target['name']}' navigate 실패 — 다음으로")
                continue

            self._process_birthday_target(
                target, template_content, image_path,
                False, msg_engine, result, on_progress, idx=nth,
            )
            # 발송 성공 시 로그에 기록
            if sent_log is not None and target.get("action") == "sent":
                sent_log.mark_sent(target["name"])

        _diag(f"send_birthday_messages(send): 완료 — sent={result['sent']}, errors={len(result['errors'])}")
        result["ok"] = True
        return result

        # (이하 unreachable — dry_run 경로는 위 return 으로 종료)
        # 아래 dead code 는 가독성 위해 남기지 않음.
        scan_rows = []
        today_rows = []
        other_rows = []

        # other(어제/내일) 들은 발송 X — 스킵 카운트만
        for r in other_rows:
            result["targets"].append({
                "name": r["name"], "day": r["day"], "row_text": r["row_text"],
                "action": "skip_not_today",
            })
            result["skipped"] += 1

        # ── Phase 2: 발송 ──
        # dry_run: enumerate 결과를 그대로 dry_run_sent 로 마킹.
        # real_send: 매 발송마다 click_first_birthday 재실행 + N번 ↓ 스킵 후 발송.
        #   이유: 신버전 카톡은 채팅창 닫힘 후 friend list selection 이 손실돼서
        #   기존 selection 에서 ↓ 가 안 먹힘. 매번 처음부터 navigate 가 가장 안정적.
        for nth, target_row in enumerate(today_rows):
            if result["sent"] >= daily_limit:
                result["reason"] = f"일일 한도 {daily_limit} 도달 — 종료"
                break

            target = {
                "step": nth,
                "name": target_row["name"],
                "day": "today",
                "row_text": target_row["row_text"][:60],
                "action": "pending",
            }

            if not dry_run:
                # 실발송: nth 번째 오늘 생일자에 selection 박기 (매번 재navigate).
                # scan 이 ↓ 로 모든 행을 enumerate 하므로 scan 종료 시점 selection
                # 은 마지막 ↓ 위치(헤더 등)에 있어 재사용 불가.
                pos_ok = self._navigate_to_nth_today_birthday(nth)
                if not pos_ok:
                    target["action"] = "error_navigate"
                    result["errors"].append(f"{target['name']}: 재navigate 실패")
                    result["targets"].append(target)
                    _diag(f"send_birthday_messages: nth={nth} '{target['name']}' navigate 실패")
                    continue

            self._process_birthday_target(
                target, template_content, image_path,
                dry_run, msg_engine, result, on_progress, idx=nth,
            )

        result["ok"] = True
        return result

    def _scan_birthday_section(self, max_steps: int = 50) -> dict:
        """친구탭에서 생일 섹션을 한 번 ↓ 로 훑어 행 목록 반환.

        Returns: {ok, reason, rows: [{name, day, row_text, section}, ...]}
            day in ("today", "other")
        """
        rows = []
        # 1) 친구탭 + 맨 위로
        if not self.reset_to_top():
            return {"ok": False, "reason": "친구탭 맨 위 스크롤 실패.", "rows": []}

        # 2) 첫 생일자 도달 (click_first_birthday 가 selection 박음)
        click_res = self.click_first_birthday()
        if not click_res["ok"]:
            return {"ok": False, "reason": click_res["reason"], "rows": []}

        first_row = click_res["row"]
        rows.append({
            "name": first_row.get("name") or "(첫 생일자)",
            "day": first_row.get("day") or "other",
            "row_text": first_row.get("row_text", ""),
            "section": "birthday",
        })

        # 3) ↓ 로 생일 섹션 끝까지 enumerate
        prev_image = self.capture_window()
        for i in range(1, max_steps):
            step = self.navigate_step(prev_image=prev_image)
            prev_image = step["cur_image"]
            if not step["moved"]:
                _diag(f"_scan_birthday_section: ↓ moved=False at step {i}")
                break
            if step["section"] != "birthday":
                _diag(f"_scan_birthday_section: 섹션 이탈({step['section']}) at step {i}")
                break
            rows.append({
                "name": step["name"],
                "day": step["day"] or "other",
                "row_text": step["row_text"],
                "section": "birthday",
            })
        return {"ok": True, "reason": "", "rows": rows}

    def _navigate_to_nth_today_birthday(self, n: int) -> bool:
        """n 번째(0-인덱스) 오늘 생일자에 selection 박기.

        매 발송 후 selection 손실 대응 — click_first_birthday 부터 다시 시작 +
        n 번 ↓ (단 어제/내일 행은 카운트 X, today 만 카운트).
        """
        click_res = self.click_first_birthday()
        if not click_res["ok"]:
            _diag(f"_navigate_to_nth: click_first 실패 — {click_res['reason']}")
            return False

        first_row = click_res["row"]
        today_seen = 1 if first_row.get("day") == "today" else 0
        if n == 0 and first_row.get("day") == "today":
            _diag(f"_navigate_to_nth(n=0): 첫 생일자가 today — 도달")
            return True

        prev_image = self.capture_window()
        for step_i in range(50):
            # 매 ↓ 전 main 재활성 (포커스 보장)
            self.win32.activate(self.win32.main_hwnd)
            time.sleep(0.2)
            step = self.navigate_step(prev_image=prev_image)
            prev_image = step["cur_image"]
            if not step["moved"]:
                _diag(f"_navigate_to_nth(n={n}): moved=False at i={step_i} (today_seen={today_seen})")
                return False
            if step["section"] != "birthday":
                _diag(f"_navigate_to_nth(n={n}): 섹션 이탈 at i={step_i}")
                return False
            if step["day"] == "today":
                if today_seen == n:
                    _diag(f"_navigate_to_nth(n={n}): 도달 — selection={step['name']!r}")
                    return True
                today_seen += 1
        _diag(f"_navigate_to_nth(n={n}): 최대 step 도달")
        return False

    def _process_birthday_target(self, target: dict, template_content: str,
                                   image_path: str, dry_run: bool,
                                   msg_engine, result: dict,
                                   on_progress, idx: int):
        """오늘 생일자 1명 처리 (발송 또는 dry_run 시뮬레이션)"""
        # 변수 치환
        contact_data = {
            "name": target["name"] or "친구",
            "category": "kakao_birthday",
        }
        try:
            message = msg_engine.substitute(template_content, contact_data)
        except Exception as e:
            target["action"] = f"error_substitute: {e}"
            result["errors"].append(f"{target['name']}: 치환 실패 ({e})")
            result["targets"].append(target)
            return

        if dry_run:
            target["action"] = "dry_run_sent"
            target["preview"] = message[:80]
            result["sent"] += 1
            result["targets"].append(target)
            if on_progress:
                on_progress(target, "dry_run_sent", idx)
            return

        # 실제 발송 — sender 주입돼 있으면 검증된 chat_hwnd/좌표 경로 사용.
        # 없으면 기존 PostMessage 기반 fallback (이름 검색 없이 동작은 하나
        # 신버전 카톡에서 채팅창 별도 윈도우 문제로 불안정).
        if self.sender is not None:
            ok = self.sender.send_to_current_selection(message, image_path=image_path)
        else:
            ok = self._send_to_current_selection(message, image_path=image_path)
        if ok:
            target["action"] = "sent"
            result["sent"] += 1
        else:
            target["action"] = "error_send"
            result["errors"].append(f"{target['name']}: 발송 실패")
        result["targets"].append(target)
        if on_progress:
            on_progress(target, target["action"], idx)

    def collect_friends_to_addressbook(self,
                                         contact_manager=None,
                                         category: str = "kakao_friend",
                                         dry_run: bool = True,
                                         max_count: int = 1000,
                                         on_progress=None,
                                         should_stop=None) -> dict:
        """
        친구 목록 자동 수집 → ContactManager 저장.

        흐름:
            reset_to_top → click_first_birthday (시작점) →
            find_friend_section_start (친구 섹션 첫 행까지) →
            ↓ 루프: 친구 행 OCR → 저장 → 다음

        Args:
            contact_manager: ContactManager 인스턴스. None 이면 dry_run 강제.
            category: 저장 시 부여할 카테고리
            dry_run: True 면 수집만, 저장 X
            max_count: 최대 수집 친구 수 (안전장치)
            on_progress: callback(target, action, idx)

        Returns:
            {
                "ok": bool,
                "added": int,
                "duplicates": int,
                "ocr_failed": int,
                "names": list[str],   # 수집된 모든 이름 (검토용)
                "dry_run": bool,
                "reason": str,
            }
        """
        from datetime import datetime
        from core.contact_manager import Contact

        result = {
            "ok": False, "added": 0, "duplicates": 0, "ocr_failed": 0,
            "names": [], "dry_run": dry_run, "reason": "",
        }

        if not dry_run and contact_manager is None:
            result["reason"] = "실제 저장 모드인데 contact_manager 가 없습니다."
            return result

        # 디버그 PNG 디렉토리 정리 — 이번 run 의 행 이미지만 유지(무한 누적 방지)
        try:
            import shutil
            from pathlib import Path as _P
            _sync_rows_dir = _P("logs/sync_rows")
            if _sync_rows_dir.exists():
                shutil.rmtree(_sync_rows_dir, ignore_errors=True)
        except Exception:
            pass

        # 1) 맨 위로
        if not self.reset_to_top():
            result["reason"] = "맨 위 스크롤 실패"
            return result

        # 2) selection 확립 — 우선 첫 생일자 클릭, 없으면 첫 친구 클릭
        click_res = self.click_first_birthday()
        if not click_res["ok"]:
            # 생일자 없음 — 친구 섹션 첫 행을 직접 찾아 클릭
            ok = self._click_first_friend_directly()
            if not ok:
                result["reason"] = (
                    f"시작점 클릭 실패 — 생일자도 없고 친구 섹션도 못 찾음. "
                    f"(생일자 시도: {click_res['reason']})"
                )
                return result

        # 3) 친구 섹션 첫 행까지 진입 (생일/채널 통과)
        ff = self.find_friend_section_start(max_steps=50)
        if not ff["reached"]:
            result["reason"] = f"친구 섹션 진입 실패 (steps={ff['steps_taken']})"
            return result

        # 3) 첫 친구 행 처리 (이미 selection 됨)
        first_step = ff["last_step"]
        seen_names_count_init = {}
        self._process_friend_target(
            first_step, contact_manager, category,
            dry_run, result, on_progress, idx=0,
            seen_names_count=seen_names_count_init,
        )

        # 4) ↓ 루프 — 끝까지
        prev_image = first_step["cur_image"]
        no_change_count = 0
        recent_names = []
        seen_names_count = {}
        # 가나다 순서 보정용 — 마지막 성공 처리된 이름 (suffix 제외 base)
        last_friend_name = first_step.get("name", "").strip() or None

        for i in range(1, max_count):
            if should_stop and should_stop():
                result["reason"] = "사용자 중단"
                break

            step = self.navigate_step(prev_image=prev_image)
            prev_image = step["cur_image"]

            if not step["moved"]:
                no_change_count += 1
                if no_change_count >= 3:
                    result["reason"] = "3회 연속 변화 없음 → 종료"
                    break
                continue
            no_change_count = 0

            # 친구 섹션 진입 후엔 섹션 분류 무시 — 생일자/채널/헤더 가
            # 또 나올 일 없음 (구조적 보장). OCR 가 친구를 birthday 로 오분류해도
            # 무조건 친구로 처리. 종료는 no_change/3회 same-name 으로만.
            #
            # 단 명백한 UI 텍스트는 안전망 역할로 종료 신호:
            cur_text = step["row_text"] or ""
            if any(sig in cur_text for sig in
                   ["친구의 생일을", "친구의 생일 을", "확인해 보세요",
                    "더보기", "전체 친구"]):
                result["reason"] = (
                    f"UI 안내문 만남 → 종료. 감지: {cur_text[:80]!r}"
                )
                break

            # 안전망: 채널 행이 섞여 들어오면 친구가 아니므로 건너뜀(종료 아님)
            if step["section"] == "channel" or "채널" in cur_text:
                continue

            # 가나다 순서 보정 제거 — 한 번 잘못된 OCR (예: 권→홍) 가
            # 후속 모든 권씨를 홍씨로 교체하는 부작용 (오류 전파).
            # Paddle 결과를 그대로 신뢰하고, 사용자가 사후 검토.
            cur_name = (step["name"] or "").strip()

            # 같은 이름 3회 연속 감지 — 마지막 행 반복 중 (↓ 가 안 움직임)
            if cur_name and len(recent_names) >= 2 and \
                    recent_names[-1] == cur_name and recent_names[-2] == cur_name:
                result["reason"] = f"같은 이름 3회 연속 ({cur_name}) → 마지막 친구로 판단, 종료"
                break

            recent_names.append(cur_name)
            if len(recent_names) > 5:
                recent_names = recent_names[-5:]

            self._process_friend_target(
                step, contact_manager, category,
                dry_run, result, on_progress, idx=i,
                seen_names_count=seen_names_count,
            )

            # 다음 비교용 — base name (suffix 부여 전) 추적
            if cur_name:
                last_friend_name = cur_name

        result["ok"] = True
        return result

    def _process_friend_target(self, step: dict, contact_manager,
                                 category: str, dry_run: bool,
                                 result: dict, on_progress, idx: int,
                                 seen_names_count: dict = None):
        """친구 1명 처리 (수집/저장).

        규칙:
          - 이번 run 에서 처음 보는 이름이고 DB 에도 없음 → 그대로 저장
          - 이번 run 에서 처음 보는데 DB 에 이미 있음 → SKIP
            (이전 run 잔여물 — suffix 안 붙임)
          - 이번 run 에서 두 번째+ → 진짜 동명이인 → " (2)", " (3)" 부여

        seen_names_count: 이번 run 에서 본 이름 카운트
        """
        from datetime import datetime
        from core.contact_manager import Contact

        # 디버그: 매 행 ROI 이미지 저장 (사용자 검증용)
        try:
            if step.get("row_image"):
                import os
                debug_dir = os.path.join("logs", "sync_rows")
                os.makedirs(debug_dir, exist_ok=True)
                safe_name = re.sub(r"[^a-zA-Z0-9가-힣]", "_",
                                   step.get("name") or "empty")[:20]
                step["row_image"].save(
                    os.path.join(debug_dir, f"{idx:04d}_{safe_name}.png")
                )
        except Exception:
            pass

        name = step["name"].strip()

        # OCR 실패 / 노이즈 필터
        if not name or len(name) < 2 or not re.search(r"[가-힣]", name):
            result["ocr_failed"] += 1
            if on_progress:
                on_progress({"name": name, "step": idx}, "ocr_failed", idx)
            return

        if seen_names_count is None:
            seen_names_count = {}

        already_seen = seen_names_count.get(name, 0) > 0
        result["names"].append(name)

        if dry_run:
            seen_names_count[name] = seen_names_count.get(name, 0) + 1
            if on_progress:
                on_progress({"name": name, "step": idx},
                            "dry_run_collected", idx)
            return

        # ── 케이스 1: 이번 run 에서 처음 보는 이름 ──
        if not already_seen:
            contact = Contact(
                name=name,
                category=category,
                memo=f"카톡 친구목록 자동수집 {datetime.now().strftime('%Y-%m-%d')}",
            )
            if contact_manager.add(contact):
                seen_names_count[name] = 1
                result["added"] += 1
                action = "added"
                display_name = name
            else:
                # DB 에 이미 있음 (이전 run 잔여) → SKIP, suffix 안 붙임
                seen_names_count[name] = 1  # 이번 run 에서도 본 걸로 기록
                result["duplicates"] += 1
                action = "duplicate_existing"
                display_name = name
        else:
            # ── 케이스 2: 이번 run 에서 두 번째+ → 진짜 동명이인 ──
            count = seen_names_count[name]
            added = False
            display_name = name
            for n in range(count + 1, count + 20):
                suffix_name = f"{name} ({n})"
                contact_n = Contact(
                    name=suffix_name,
                    category=category,
                    memo=f"카톡 친구목록 자동수집 {datetime.now().strftime('%Y-%m-%d')}",
                )
                if contact_manager.add(contact_n):
                    seen_names_count[name] = n
                    result["added"] += 1
                    action = "added_homonym"
                    display_name = suffix_name
                    added = True
                    break
            if not added:
                result["duplicates"] += 1
                action = "duplicate"

        if on_progress:
            on_progress({"name": display_name, "step": idx}, action, idx)

    # ── 디버그 / 운영 보조 ──

    def dump_screen(self, save_path: str = None) -> dict:
        """
        현재 화면 스크린샷 + OCR 결과 + 주요 헤더 위치 한 번에 보기

        Returns:
            {
                "screenshot_path": ...,
                "window_rect": {...},
                "birthday": {...},
                "friend_count": int,
                "gift_buttons": [...],
                "all_hits": [...]
            }
        """
        rect = self.get_window_rect()
        img = self.capture_window()
        if save_path is None:
            import tempfile
            save_path = self.capture.save_screenshot(img, "kakao_friends_debug")
        else:
            img.save(save_path)

        hits = self.find_text_hits(image=img)
        bday = self.get_section_count(self.SECTION_BIRTHDAY, hits=hits)
        friend_n = self.get_friend_count(hits=hits)
        gift_btns = self.find_gift_buttons(hits=hits)

        return {
            "screenshot_path": save_path,
            "window_rect": rect,
            "birthday": bday,
            "friend_count": friend_n,
            "gift_buttons": [{"text": h.text, "x": h.x, "y": h.y} for h in gift_btns],
            "hits_summary": [
                f"[{h.confidence}%] ({h.x},{h.y}) {h.text!r}"
                for h in hits[:50]
            ],
        }
