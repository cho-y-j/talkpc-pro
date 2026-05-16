"""
KakaoSender - 카카오톡 자동 발송 모듈 (Win32 API 기반)

핵심 변경:
- pyautogui 마우스 이동 → Win32 PostMessage (커서 이동 없음)
- 물리적 마우스 패턴이 없어 카카오톡 자동화 탐지 회피
- 향상된 안티디텍트: 세션 분할, 가변 딜레이, 배치 관리

안전장치:
- 일일 발송 한도
- 배치별 휴식 (N명마다 장시간 휴식)
- 에러 발생 시 즉시 정지 + 콜백
"""

import re
import time
import random
import platform

import win32con

from core.kakao_win32 import KakaoWin32, _log as _debug_log
from core.screen_capture import ScreenCapture
from core.ocr_engine import OCREngine
from pathlib import Path

import tempfile
_OCR_PATH = Path(tempfile.gettempdir()) / "kakao_ocr_capture.png"


class SendResult:
    """발송 결과 데이터"""

    SUCCESS = "success"
    FAILED_NOT_FOUND = "not_found"
    FAILED_OCR = "ocr_error"
    FAILED_SEND = "send_error"
    FAILED_SAFETY = "safety_stop"
    SKIPPED = "skipped"

    def __init__(self, contact_name: str, status: str, message: str = "", detail: str = ""):
        self.contact_name = contact_name
        self.status = status
        self.message = message
        self.detail = detail
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "contact_name": self.contact_name,
            "status": self.status,
            "message": self.message[:50] + "..." if len(self.message) > 50 else self.message,
            "detail": self.detail,
            "timestamp": self.timestamp
        }


class SafetyError(Exception):
    """안전 장치 발동 시 발생하는 예외"""
    pass


class KakaoSender:
    """
    카카오톡 자동 발송기 (Win32 API 기반)

    - PostMessage로 클릭 → 마우스 커서 이동 없음
    - 클립보드 + Ctrl+V → 한글 텍스트 입력
    - 세션 기반 배치 관리 → 카카오톡 서버 탐지 회피
    """

    def __init__(self, coordinates: dict, config: dict = None):
        self.coords = coordinates
        self.config = config or {}

        # Win32 엔진 초기화
        click_mode = self.config.get("anti_detect", {}).get(
            "click_mode", KakaoWin32.MODE_POSTMESSAGE
        )
        self.win32 = KakaoWin32(click_mode=click_mode)
        self.win32.find_main_window()

        # OCR (스크린샷 기반 검증은 유지)
        self.capture = ScreenCapture()
        self.ocr = OCREngine()

        # ── 딜레이 설정 ──
        sending = self.config.get("sending", {})
        self.delay_min = sending.get("delay_min", 30)
        self.delay_max = sending.get("delay_max", 90)
        self.retry_count = sending.get("retry_count", 1)

        # ── 안티디텍트 설정 ──
        anti = self.config.get("anti_detect", {})
        self.action_delay_min = anti.get("action_delay_min", 0.3)
        self.action_delay_max = anti.get("action_delay_max", 1.0)
        self.rest_every = anti.get("rest_every", 15)
        self.rest_min = anti.get("rest_min", 180)
        self.rest_max = anti.get("rest_max", 420)
        self.daily_limit = anti.get("daily_limit", 150)
        # 경고 누적 한도 — 한 세션에서 N회 누적되면 강제 종료
        self.warning_threshold = anti.get("warning_threshold", 3)
        self.warning_cooldown = anti.get("warning_cooldown", 60)

        # OCR 검증 모드: "strict"=실패시 건너뜀, "skip"=검증 안 함
        self.ocr_mode = self.config.get("ocr", {}).get("verify_mode", "skip")

        # ── 상태 ──
        self._stop_flag = False
        self._safety_error = None
        self._send_count = 0
        self._warning_count_session = 0
        self._on_safety_stop = None

    def on_safety_stop(self, callback):
        """안전 정지 콜백 등록"""
        self._on_safety_stop = callback

    def stop(self):
        self._stop_flag = True

    def resume(self):
        self._stop_flag = False
        self._safety_error = None
        self._send_count = 0
        self._warning_count_session = 0

    def _on_warning(self, where: str):
        """경고 팝업 감지 시 누적 카운터 증가 + 임계 도달 시 SafetyError.

        Args:
            where: 경고 발생 위치 ("채팅방 진입" / "전송 후" 등) — 로그용
        """
        self._warning_count_session += 1
        _debug_log(
            f"⚠️ 경고 누적 {self._warning_count_session}/{self.warning_threshold}"
            f" ({where})"
        )
        if self._warning_count_session >= self.warning_threshold:
            raise SafetyError(
                f"경고 {self.warning_threshold}회 누적 — 카톡 의심도 임계 도달, 세션 종료"
            )

    # ── 딜레이 (사람처럼) ──

    def _human_delay(self, min_s: float = None, max_s: float = None):
        """랜덤 딜레이"""
        lo = min_s if min_s is not None else self.action_delay_min
        hi = max_s if max_s is not None else self.action_delay_max
        time.sleep(random.uniform(lo, hi))

    def should_rest(self) -> bool:
        """N명마다 긴 휴식이 필요한지"""
        return (self.rest_every > 0
                and self._send_count > 0
                and self._send_count % self.rest_every == 0)

    def take_rest(self) -> float:
        """긴 휴식 (배치 간 쉬기)"""
        rest = random.uniform(self.rest_min, self.rest_max)
        _debug_log(f"배치 휴식: {rest:.0f}초 ({self._send_count}명 발송 후)")
        time.sleep(rest)
        return rest

    def check_daily_limit(self) -> bool:
        """일일 발송 한도 체크"""
        return self.daily_limit <= 0 or self._send_count < self.daily_limit

    # ── 안전한 조작 메서드 (Win32 기반) ──

    def _safe_click(self, x: int, y: int, clicks: int = 1):
        """
        Win32 클릭 (마우스 커서 이동 없음)
        PostMessage 모드: 완전 무커서
        Stealth 모드: 커서 숨김 + 빠른 이동/클릭/복원
        """
        try:
            self._check_stop()
            if clicks >= 2:
                self.win32.double_click(x, y)
            else:
                self.win32.click(x, y)
            self._human_delay(0.2, 0.5)
        except Exception as e:
            _debug_log(f"_safe_click 에러: {e}")
            raise

    def _activate_kakao(self):
        """카카오톡 메인 창 활성화 (발송 중에는 포그라운드 필요)"""
        if not self.win32.main_hwnd:
            self.win32.find_main_window()
        if self.win32.main_hwnd:
            self.win32.activate(self.win32.main_hwnd)
            _debug_log("카카오톡 활성화 완료")
        else:
            _debug_log("카카오톡 창을 찾을 수 없음")

    def _safe_type_text(self, text: str):
        """Win32 클립보드 + Ctrl+V (한글 지원)"""
        try:
            _debug_log(f"type_text 시작: '{text[:30]}'")
            self.win32.paste_text(text)
            time.sleep(0.5)
        except Exception as e:
            _debug_log(f"type_text 에러: {e}")
            raise

    def _safe_clear_input(self):
        """입력 필드 전체 삭제 (Win32 PostMessage)"""
        try:
            hwnd = self.win32.chat_hwnd or self.win32.main_hwnd
            self.win32.clear_input(hwnd)
            _debug_log("clear_input 완료")
            time.sleep(0.3)
        except Exception as e:
            _debug_log(f"clear_input 에러: {e}")
            raise

    def _safe_press(self, key: str):
        """키 입력 (Win32 PostMessage)"""
        try:
            vk_map = {
                "enter": win32con.VK_RETURN,
                "return": win32con.VK_RETURN,
                "escape": win32con.VK_ESCAPE,
                "delete": win32con.VK_DELETE,
                "tab": win32con.VK_TAB,
                "home": win32con.VK_HOME,
                "end": win32con.VK_END,
            }
            vk = vk_map.get(key)
            if vk is None:
                _debug_log(f"_safe_press: 알 수 없는 키 '{key}'")
                return

            hwnd = self.win32.chat_hwnd or self.win32.main_hwnd
            self.win32.press_key(hwnd, vk)
            time.sleep(0.3)
        except Exception as e:
            _debug_log(f"_safe_press 에러: {e}")
            raise

    def _check_stop(self):
        """중지 플래그 체크"""
        if self._stop_flag:
            raise SafetyError("사용자가 발송을 중지했습니다.")

    # ── 카카오톡 조작 ──

    def click_search_icon(self):
        """돋보기(검색) 아이콘 클릭 — 항상 1회만 (go_back에서 이미 검색 닫음)"""
        self._check_stop()
        coord = self.coords.get("search_icon", {})
        _debug_log(f"click_search_icon: ({coord.get('x')}, {coord.get('y')})")

        self._safe_click(coord["x"], coord["y"])
        _debug_log("click_search_icon: 검색 모드 열기")
        self._human_delay(1.0, 1.5)

    def search_contact(self, name: str) -> bool:
        """이름으로 연락처 검색 (검색창은 항상 새로 열린 상태)"""
        self._check_stop()
        _debug_log(f"search_contact: '{name}' 검색 시작")
        coord = self.coords.get("search_input", {})
        self._safe_click(coord["x"], coord["y"])
        self._human_delay(0.3, 0.5)

        _debug_log("이름 입력")
        self._safe_type_text(name)
        _debug_log("이름 입력 완료, 검색 결과 대기...")
        self._human_delay(1.5, 2.5)  # 검색 결과 로딩 대기 충분히
        return True

    def verify_search_result(self, target_name: str) -> dict:
        """
        OCR 로 검색 결과 첫 행과 검색 입력 이름 비교.

        ★ PaddleOCR 95%+ 파이프라인 사용 (paddle_ocr_helper.verify_name_match).
           실패 시 Tesseract 폴백 유지.

        Args:
            target_name: 검색에 입력한 이름 (예: "안덕현")

        Returns:
            {
                "found": bool,             # 매칭 성공
                "matched_text": str,       # OCR 한 이름
                "match_level": str,        # exact|contain|fuzzy|none
                "confidence": float,
                "engine": str,             # paddle|tesseract
                "skipped": bool,           # OCR 자체 불가 (안전 통과)
            }
        """
        try:
            first_result = self.coords.get("first_result", {})
            if not first_result:
                return {"found": True, "skipped": True}

            fr_x = first_result["x"]
            fr_y = first_result["y"]

            # 검색 결과 ROI — 친구탭 행 크기 (~243x56) 와 비슷하게 작게 잡기.
            # 너무 크면 5x 확대 후 paddle_inference 가 silent fail (빈 결과 반환).
            # CLAUDE.md "95% 검증된 파이프라인" 의 입력 크기 가정과 동일하게.
            #
            # learned_positions.first_result.y 가 결과 행 중심에 정확히 못 잡혀도
            # ±40px 범위면 결과 행이 영역 안에 들어옴.
            kx = self.win32.get_window_rect(self.win32.main_hwnd) \
                if self.win32.main_hwnd else None
            if kx:
                win_x = kx["x"]
                win_w = kx["width"]
                # X: 프로필 이미지(~20%) ~ 우측 여백 전 (78%) — 친구탭과 동일 비율
                x1 = win_x + int(win_w * 0.20)
                x2 = win_x + int(win_w * 0.78)
                # Y: 결과 행 중심 ± 40 (총 80px) — 첫 행만 잡고 paddle 처리 가능 크기
                y1 = max(0, fr_y - 40)
                y2 = fr_y + 40
            else:
                x1 = max(0, fr_x - 80)
                x2 = fr_x + 200
                y1 = max(0, fr_y - 40)
                y2 = fr_y + 40

            # PaddleOCR 우선 시도 (2회 — UI 갱신 시간 고려)
            try:
                from core.paddle_ocr_helper import verify_name_match
                paddle_available = True
            except ImportError:
                paddle_available = False

            last_result = None
            for attempt in range(2):
                _debug_log(f"OCR 캡처 시도 {attempt+1}: "
                           f"({x1},{y1})~({x2},{y2}) [{x2-x1}x{y2-y1}px]")
                screenshot = self.capture.capture_region(x1, y1, x2, y2)
                screenshot.save(str(_OCR_PATH))

                # 1) Paddle 시도
                if paddle_available:
                    try:
                        m = verify_name_match(screenshot, target_name)
                        last_result = {
                            "found": m["matched"],
                            "matched_text": m["ocr_name"],
                            "extracted_text": m["ocr_text"],
                            "match_level": m["match_level"],
                            "confidence": m["confidence"],
                            "engine": m["engine"],
                        }
                        _debug_log(
                            f"Paddle 결과: matched={m['matched']} "
                            f"name='{m['ocr_name']}' level={m['match_level']} "
                            f"conf={m['confidence']:.2f}"
                        )
                        if m["matched"]:
                            return last_result
                    except Exception as e:
                        _debug_log(f"Paddle 시도 {attempt+1} 에러: {e}")

                # 2) Tesseract 폴백
                if self.ocr.available:
                    try:
                        tess = self.ocr.verify_name_in_results(
                            screenshot, target_name
                        )
                        _debug_log(
                            f"Tesseract 폴백: found={tess.get('found')} "
                            f"text='{tess.get('matched_text')}'"
                        )
                        if tess.get("found"):
                            tess["engine"] = "tesseract"
                            return tess
                        last_result = last_result or tess
                    except Exception as e:
                        _debug_log(f"Tesseract 에러: {e}")

                if attempt == 0:
                    _debug_log("OCR 1차 실패 — 1.5초 대기 후 재시도")
                    time.sleep(1.5)

            # 두 번 모두 실패
            if last_result is None:
                return {"found": False, "skipped": True,
                        "error": "OCR 엔진 모두 사용 불가"}

            # 검증 실패 시 ROI 캡처를 logs/verify_failed/ 에 저장 — 사용자 디버깅용.
            # 실제로 어떤 화면이 잡혔는지 사후 확인 가능.
            if not last_result.get("found"):
                try:
                    from datetime import datetime
                    fail_dir = Path("logs/verify_failed")
                    fail_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = re.sub(r'[^\w가-힣]', '_', target_name)[:20]
                    fail_path = fail_dir / f"{ts}_{safe_name}.png"
                    screenshot.save(str(fail_path))
                except Exception:
                    pass

            return last_result

        except Exception as e:
            _debug_log(f"verify_search_result 예외: {e}")
            return {"found": False, "error": str(e)}

    def click_search_result(self):
        """첫 번째 검색 결과 더블클릭 (채팅방 진입)"""
        self._check_stop()
        coord = self.coords.get("first_result", {})
        x, y = coord["x"], coord["y"]
        _debug_log(f"click_search_result: ({x}, {y})")

        # 카카오톡 활성화
        try:
            self._activate_kakao()
        except Exception as e:
            _debug_log(f"활성화 실패 (무시): {e}")
        time.sleep(0.3)

        # Win32 더블클릭
        self._safe_click(x, y, clicks=2)
        _debug_log("더블클릭 완료")

        self._human_delay(1.5, 2.5)  # 채팅방 열리기 대기

        # 채팅창 감지 + 메인 카카오톡 위치로 이동
        self.win32.get_foreground_as_chat()
        try:
            self.win32.position_chat_to_main()
        except Exception as e:
            _debug_log(f"채팅창 배치 실패 (무시): {e}")

        _debug_log("채팅방 열림 완료")

    def type_message(self, message: str):
        """메시지 입력"""
        self._check_stop()
        coord = self.coords.get("message_input", {})
        _debug_log(f"type_message: ({coord.get('x')}, {coord.get('y')})")
        self._safe_click(coord["x"], coord["y"])
        self._human_delay(0.2, 0.5)
        self._safe_type_text(message)
        self._human_delay(0.3, 0.8)

    def send_message(self):
        """메시지 전송 (전송 버튼 클릭)"""
        self._check_stop()
        coord = self.coords.get("send_enter", {})
        _debug_log(f"send_message: ({coord.get('x')}, {coord.get('y')})")
        self._human_delay(0.2, 0.5)
        self._safe_click(coord["x"], coord["y"])
        self._human_delay(0.5, 1.0)

    def detect_warning_popup(self) -> bool:
        """
        카���오톡 경고/차단 팝업 감지
        화면 중앙 부근에 경고 다이얼로그가 떠있는지 OCR로 확인
        """
        try:
            import pyautogui
            sw, sh = pyautogui.size()

            # 화면 중앙 넓은 영역 캡처 (팝업은 보통 중앙에 뜸)
            cx, cy = sw // 2, sh // 2
            x1 = max(0, cx - 250)
            y1 = max(0, cy - 150)
            x2 = cx + 250
            y2 = cy + 150

            screenshot = self.capture.capture_region(x1, y1, x2, y2)

            if not self.ocr.available:
                return False

            text = self.ocr.extract_text(screenshot)
            _debug_log(f"팝업 감지 OCR: '{text[:80]}'")

            # 카카오��� 경고 키워드
            warning_keywords = [
                "경고", "차단", "제한", "스팸", "비정상",
                "일시적", "이용제한", "메시지를 보낼 수 없",
                "확인", "신고"
            ]
            for kw in warning_keywords:
                if kw in text:
                    _debug_log(f"경고 팝업 감지! 키워드: '{kw}'")
                    return True

            return False
        except Exception as e:
            _debug_log(f"팝��� 감지 에러: {e}")
            return False

    def dismiss_popup(self):
        """경고 팝업 ��기 (확인 버튼 클릭 또는 Escape)"""
        try:
            import pyautogui
            sw, sh = pyautogui.size()
            # 팝업 '확인' 버튼 위치 (화면 중앙 하단)
            self._safe_click(sw // 2, sh // 2 + 80)
            time.sleep(0.5)
            _debug_log("팝업 닫기 완료")
        except Exception as e:
            _debug_log(f"팝업 닫기 에러: {e}")

    def paste_image(self, image_path: str):
        """이미지 클립보드 복사 → 붙여넣기 → 전송"""
        self._check_stop()
        _debug_log(f"paste_image: {image_path}")

        # 카톡 PC 신버전은 채팅창이 별도 윈도우 — main_hwnd 만 activate 하면
        # 채팅창이 비활성/뒤로 가서 keybd_event Ctrl+V 가 채팅 입력창에
        # 도달 못 함. chat_hwnd 가 있으면 그걸 우선 활성화.
        chat_hwnd = self.win32.chat_hwnd or self.win32.main_hwnd
        if chat_hwnd:
            self.win32.activate(chat_hwnd)
            _debug_log(f"paste_image: 채팅창 활성화 hwnd={chat_hwnd}")
        time.sleep(0.3)

        # 메시지 입력창 클릭 (포커스) — stealth 모드 (실제 마우스 클릭).
        # PostMessage 클릭은 호버만 발생해 포커스가 안 잡히므로 Ctrl+V 가
        # 입력창이 아닌 다른 위치로 갈 수 있음.
        coord = self.coords.get("message_input", {})
        old_mode = self.win32.click_mode
        self.win32.click_mode = self.win32.MODE_STEALTH
        try:
            self.win32.click(coord["x"], coord["y"])
        finally:
            self.win32.click_mode = old_mode
        time.sleep(0.4)

        # 이미지 클립보드 + Ctrl+V
        self.win32.paste_image(image_path)
        _debug_log("이미지 붙여넣기 완료")
        time.sleep(2.0)  # 이미지 전송 확인 팝업 대기

        # 이미지 전송 버튼 클릭 — stealth 모드 (실제 마우스 이벤트) 필수.
        # 카톡 이미지 전송 팝업은 별도 자식 hwnd 로 뜨는데 PostMessage 클릭은
        # 호버만 발생하고 버튼 액션이 안 먹힘 (CLAUDE.md "PostMessage = 호버만,
        # selection/액션은 stealth").
        img_coord = self.coords.get("image_send", {})
        old_mode = self.win32.click_mode
        self.win32.click_mode = self.win32.MODE_STEALTH
        try:
            if img_coord and "x" in img_coord:
                self.win32.click(img_coord["x"], img_coord["y"])
                _debug_log(
                    f"이미지 전송 버튼 클릭(stealth): "
                    f"({img_coord['x']}, {img_coord['y']})"
                )
            else:
                send_coord = self.coords.get("send_enter", {})
                if send_coord and "x" in send_coord:
                    self.win32.click(send_coord["x"], send_coord["y"])
                else:
                    self._safe_press("enter")
        finally:
            self.win32.click_mode = old_mode
        time.sleep(1.0)

    def go_back(self):
        """채팅방 나가기 → 홈 화면으로 복귀"""
        self._check_stop()
        self._human_delay(0.3, 0.8)

        # 1. 채팅방 닫기 (뒤로가기 버튼 클릭) — 카톡 PC 신버전은 채팅창이
        # 별도 윈도우. 좌표가 같은 위치라도 메인 창이 포그라운드면
        # PostMessage 가 메인 창의 X 버튼으로 가서 카톡 자체가 닫히는 사고.
        # 채팅창 활성화 + stealth 클릭으로 채팅창 X 버튼 확실히 클릭.
        coord = self.coords.get("back_button", {})
        if coord and "x" in coord:
            if self.win32.chat_hwnd:
                self.win32.activate(self.win32.chat_hwnd)
                time.sleep(0.2)
            old_mode = self.win32.click_mode
            self.win32.click_mode = self.win32.MODE_STEALTH
            try:
                self.win32.click(coord["x"], coord["y"])
            finally:
                self.win32.click_mode = old_mode
        self._human_delay(0.5, 0.8)

        # 2. 검색 모드 닫기 (돋보기 클릭 — Escape 대신)
        search_coord = self.coords.get("search_icon", {})
        if search_coord and "x" in search_coord:
            self.win32.click(search_coord["x"], search_coord["y"])
            time.sleep(0.3)

        self._human_delay(0.3, 0.5)

        # 채팅창 핸들 초기화
        self.win32.chat_hwnd = None

    def reset_to_home(self):
        """
        카카오톡 메인 창 핸들 확보 (홈 화면 복귀).

        ⚠️ 검색 토글 동작은 제거됨. ensure_ready_state() 가 detect_screen_state()
        로 정확한 상태 판단 후 검색창 열림 시에만 search_icon 1회 클릭.
        강제 2회 토글은 시작 상태/타이밍에 따라 결과가 정반대가 되어 검색창
        을 못 여는 사고를 일으킴.
        """
        _debug_log("reset_to_home: 메인 창 핸들 확보")
        hwnd = self.win32.main_hwnd
        if not hwnd:
            self.win32.find_main_window()

    @property
    def kakao_friends(self):
        """KakaoFriends 인스턴스 — 시작 상태 자동화용 (lazy init)"""
        if not hasattr(self, "_kakao_friends_inst") or \
                self._kakao_friends_inst is None:
            from core.kakao_friends import KakaoFriends
            self._kakao_friends_inst = KakaoFriends(
                self.win32, self.ocr, self.capture,
            )
        return self._kakao_friends_inst

    def _do_send(self, name: str, message: str, image_path: str = None) -> SendResult:
        """
        실제 발송 1회 시도 (내부용)
        Returns: SendResult (SUCCESS, FAILED_*, WARNING)
        """
        # 0. 카카오톡 활성화 + 홈 화면 복귀
        self._activate_kakao()
        if self._send_count == 0:
            self.reset_to_home()

            # 0.5. 첫 발송 — 친구탭 + 검색창 닫힘 자동 보장
            try:
                ready = self.kakao_friends.ensure_ready_state(
                    friends_icon=self.coords.get("friends_tab_icon"),
                    search_icon=self.coords.get("search_icon"),
                )
                if ready["ok"]:
                    if ready["actions"]:
                        _debug_log(f"준비 상태 자동 정상화: {ready['actions']}")
                else:
                    _debug_log(
                        f"준비 상태 자동 정상화 실패 (계속 진행): "
                        f"{ready['final_state']}"
                    )
            except Exception as e:
                _debug_log(f"ensure_ready_state 예외 (무시하고 진행): {e}")

        # 1. 돋보기 클릭
        self.click_search_icon()

        # 2. 이름 검색
        self.search_contact(name)

        # 3. OCR 검증
        self._check_stop()
        verification = self.verify_search_result(name)
        verified = verification.get("found", False)

        if verified:
            _debug_log(f"OCR 검증 성공: '{name}'")
        else:
            _debug_log(f"OCR 검증 실패: {verification}")
            # 검색 모드 닫기 (돋보기 클릭)
            try:
                search_coord = self.coords.get("search_icon", {})
                if search_coord and "x" in search_coord:
                    self.win32.click(search_coord["x"], search_coord["y"])
                    time.sleep(0.3)
            except Exception:
                pass
            self._send_count += 1
            return SendResult(
                name, SendResult.FAILED_NOT_FOUND,
                detail=f"검색 결과에서 '{name}'을 찾을 수 없음"
            )

        # 4. 검색 결과 더블클릭 → 채팅방
        _debug_log(f"'{name}' 더블클릭 시작")
        self.click_search_result()

        # 4.5. 채팅방 진입 후 경고 팝업 체크
        if self.detect_warning_popup():
            _debug_log(f"'{name}' 채팅방 진입 시 경고 감지!")
            self.dismiss_popup()
            self.go_back()
            self._on_warning("채팅방 진입")  # 누적 → 임계 시 SafetyError
            time.sleep(self.warning_cooldown)
            return SendResult(
                name, "warning",
                detail="채팅방 진입 시 경고 팝업"
            )

        # 5. 메시지 입력 → 전송
        if message:
            self.type_message(message)
            self.send_message()

            # 5.5. 전송 직후 경고 팝업 체크
            time.sleep(0.5)
            if self.detect_warning_popup():
                _debug_log(f"'{name}' 전송 후 경고 감지!")
                self.dismiss_popup()
                self.go_back()
                self._on_warning("전송 후")  # 누적 → 임계 시 SafetyError
                time.sleep(self.warning_cooldown)
                return SendResult(
                    name, "warning",
                    detail="전송 후 경고 팝업"
                )

        # 6. 이미지 (있으면)
        if image_path:
            _debug_log(f"이미지 첨부: {image_path}")
            self.paste_image(image_path)

        # 7. 뒤로가기
        self.go_back()

        self._send_count += 1
        return SendResult(name, SendResult.SUCCESS, message=message)

    def send_to_contact(self, name: str, message: str, image_path: str = None,
                        max_retry: int = 3) -> SendResult:
        """
        한 명에게 메시지 발송 (경고 시 자동 재시도)

        경고 팝업 → 팝업 닫기 → 대기 → 재시도 (최대 max_retry회)
        시도할 때마��� 대기 시간 증가: 10초 → 30초 → 60초
        """
        retry_delays = [10, 30, 60]  # 재시도 대기 시간 (점진적 증가)

        for attempt in range(max_retry):
            try:
                _debug_log(f"=== {name}에게 발송 시도 {attempt+1}/{max_retry} ===")
                result = self._do_send(name, message, image_path)

                if result.status == "warning":
                    # 경고 → 재시도
                    if attempt < max_retry - 1:
                        wait = retry_delays[min(attempt, len(retry_delays) - 1)]
                        _debug_log(f"경고 감지! {wait}초 대기 후 재시도")
                        time.sleep(wait)
                        continue
                    else:
                        # 최대 재시도 초과 → 실패로 기록
                        _debug_log(f"'{name}' 최대 재시도 {max_retry}회 초과 → 실패")
                        self._send_count += 1
                        return SendResult(
                            name, SendResult.FAILED_SEND,
                            detail=f"경고 팝업 {max_retry}회 연속 - 전송 실패"
                        )
                else:
                    # 성공이든 다른 실패든 그대로 반환
                    return result

            except SafetyError as e:
                self._stop_flag = True
                self._safety_error = str(e)
                if self._on_safety_stop:
                    self._on_safety_stop(str(e))
                return SendResult(
                    name, SendResult.FAILED_SAFETY,
                    detail=f"안전 정지: {e}"
                )
            except Exception as e:
                _debug_log(f"[ERROR] {name} 발송 중 에러 (시도 {attempt+1}): {e}")
                # 검색 모드 닫기 (돋보기 클릭)
                try:
                    search_coord = self.coords.get("search_icon", {})
                    if search_coord and "x" in search_coord:
                        self.win32.click(search_coord["x"], search_coord["y"])
                        time.sleep(0.3)
                except Exception:
                    pass
                # 에러도 재시도
                if attempt < max_retry - 1:
                    wait = retry_delays[min(attempt, len(retry_delays) - 1)]
                    _debug_log(f"에러 발생, {wait}초 대기 후 재시도")
                    time.sleep(wait)
                    continue
                else:
                    self._send_count += 1
                    return SendResult(
                        name, SendResult.FAILED_SEND,
                        detail=f"발송 실패 ({max_retry}회 시도): {str(e)}"
                    )

        # 여기 오면 안 되지만 안전장치
        self._send_count += 1
        return SendResult(name, SendResult.FAILED_SEND, detail="알 수 없는 오류")

    def random_delay(self):
        """
        메시지 간 랜덤 딜레이 (비균등 분포)
        - 70%: 기본 범위 (delay_min ~ delay_max)
        - 20%: 짧은 딜레이 (기본의 50~80%)
        - 10%: 긴 딜레이 (기본의 150~300%) → 사람처럼 가끔 쉬는 패턴
        """
        roll = random.random()
        if roll < 0.10:
            # 10%: 길게 쉬기 (자연스러운 패턴)
            delay = random.uniform(self.delay_max * 1.5, self.delay_max * 3.0)
            _debug_log(f"random_delay: {delay:.1f}초 (긴 휴식)")
        elif roll < 0.30:
            # 20%: 짧게
            delay = random.uniform(self.delay_min * 0.5, self.delay_max * 0.8)
            _debug_log(f"random_delay: {delay:.1f}초 (짧은)")
        else:
            # 70%: 기본
            delay = random.uniform(self.delay_min, self.delay_max)
            _debug_log(f"random_delay: {delay:.1f}초 (기본)")
        time.sleep(delay)
        return delay
