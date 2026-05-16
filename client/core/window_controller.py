"""
WindowController - 카카오톡 창 관리 모듈
Mac (AppleScript) / Windows (win32gui) 크로스 플랫폼 지원
"""

import platform
import subprocess
import json
import os
from pathlib import Path

try:
    import pyautogui
except ImportError:
    pyautogui = None


class WindowController:
    """카카오톡 창 위치/크기를 강제 고정하는 컨트롤러"""

    KAKAO_APP_NAME_MAC = "KakaoTalk"
    KAKAO_APP_NAME_WIN = "카카오톡"
    KAKAO_WINDOW_TITLE_WIN = "카카오톡"
    # 우리 앱 창을 카카오톡으로 오인하지 않기 위한 제외 키워드
    EXCLUDE_TITLES = ["TalkPC", "Auto Messenger", "자동 발송"]

    def __init__(self, config: dict = None):
        self.system = platform.system()  # "Darwin" (Mac) or "Windows"
        self.config = config or {}
        self.screen_width = 0
        self.screen_height = 0
        self.dpi_scale = 1.0
        self.kakao_rect = {}  # {x, y, width, height}
        self._detect_screen()

    def _detect_screen(self):
        """모니터 해상도 및 DPI 스케일링 감지"""
        if pyautogui:
            self.screen_width, self.screen_height = pyautogui.size()
        else:
            # fallback
            self.screen_width = 1920
            self.screen_height = 1080

        if self.system == "Windows":
            try:
                import ctypes
                self.dpi_scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0
            except Exception:
                self.dpi_scale = 1.0
        elif self.system == "Darwin":
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType", "-json"],
                    capture_output=True, text=True, timeout=5
                )
                data = json.loads(result.stdout)
                displays = data.get("SPDisplaysDataType", [])
                for gpu in displays:
                    for disp in gpu.get("spdisplays_ndrvs", []):
                        res = disp.get("_spdisplays_resolution", "")
                        if "Retina" in res:
                            self.dpi_scale = 2.0
                            break
            except Exception:
                self.dpi_scale = 1.0

    def get_screen_info(self) -> dict:
        """현재 화면 정보 반환"""
        return {
            "system": self.system,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "dpi_scale": self.dpi_scale
        }

    def calculate_kakao_position(self) -> dict:
        """카카오톡 창 위치/크기 결정 - 저장된 위치 우선, 없으면 우측 상단"""
        # 저장된 위치가 있으면 사용
        saved = self._load_saved_position()
        if saved:
            self.kakao_rect = saved
            return self.kakao_rect

        # 없으면 자동 계산 (우측 상단)
        kakao_w = self.config.get("kakao_window", {}).get("width", 420)
        kakao_h = self.config.get("kakao_window", {}).get("height", 700)
        margin_right = self.config.get("kakao_window", {}).get("margin_right", 20)
        margin_top = self.config.get("kakao_window", {}).get("margin_top", 40)

        kakao_x = self.screen_width - kakao_w - margin_right
        kakao_y = margin_top

        # 화면 밖으로 나가지 않게 보정
        if kakao_x + kakao_w > self.screen_width:
            kakao_x = self.screen_width - kakao_w - 10
        if kakao_x < 0:
            kakao_x = 10
        if kakao_y + kakao_h > self.screen_height:
            kakao_h = self.screen_height - kakao_y - 50

        self.kakao_rect = {
            "x": kakao_x,
            "y": kakao_y,
            "width": kakao_w,
            "height": kakao_h
        }
        return self.kakao_rect

    def save_current_kakao_position(self) -> bool:
        """현재 카카오톡 창 위치를 감지하여 저장"""
        rect = self._get_current_kakao_rect()
        if not rect:
            return False
        self.kakao_rect = rect
        self._save_position(rect)
        return True

    def _get_current_kakao_rect(self) -> dict:
        """현재 카카오톡 창의 실제 위치/크기 가져오기"""
        if self.system == "Darwin":
            try:
                script = '''
                tell application "System Events"
                    tell process "KakaoTalk"
                        set p to position of window 1
                        set s to size of window 1
                        return (item 1 of p) & "," & (item 2 of p) & "," & (item 1 of s) & "," & (item 2 of s)
                    end tell
                end tell
                '''
                result = subprocess.run(["osascript", "-e", script],
                                       capture_output=True, text=True, timeout=5)
                parts = result.stdout.strip().split(",")
                if len(parts) == 4:
                    return {
                        "x": int(parts[0].strip()),
                        "y": int(parts[1].strip()),
                        "width": int(parts[2].strip()),
                        "height": int(parts[3].strip())
                    }
            except Exception:
                pass
        elif self.system == "Windows":
            try:
                import win32gui
                def callback(hwnd, results):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if self._is_kakao_window(title):
                            results.append(hwnd)
                results = []
                win32gui.EnumWindows(callback, results)
                if results:
                    rect = win32gui.GetWindowRect(results[0])
                    return {
                        "x": rect[0], "y": rect[1],
                        "width": rect[2] - rect[0],
                        "height": rect[3] - rect[1]
                    }
            except Exception:
                pass
        return None

    def _save_position(self, rect: dict):
        """카카오톡 창 위치를 파일로 저장"""
        save_path = Path(os.path.dirname(os.path.dirname(__file__))) / "config" / "kakao_position.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(rect, f, indent=2)

    def _load_saved_position(self) -> dict:
        """저장된 카카오톡 창 위치 불러오기"""
        save_path = Path(os.path.dirname(os.path.dirname(__file__))) / "config" / "kakao_position.json"
        if save_path.exists():
            try:
                with open(save_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def find_kakao_window(self) -> bool:
        """카카오톡 창이 열려있는지 확인"""
        if self.system == "Darwin":
            return self._find_kakao_mac()
        elif self.system == "Windows":
            return self._find_kakao_win()
        return False

    def _find_kakao_mac(self) -> bool:
        """Mac에서 카카오톡 프로세스 확인"""
        try:
            script = '''
            tell application "System Events"
                set appList to name of every process
                if appList contains "KakaoTalk" then
                    return "found"
                else
                    return "not_found"
                end if
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )
            return "found" in result.stdout.strip()
        except Exception:
            return False

    def _is_kakao_window(self, title: str) -> bool:
        """카카오톡 창인지 판별 (우리 앱 제외)"""
        if self.KAKAO_WINDOW_TITLE_WIN not in title:
            return False
        for exclude in self.EXCLUDE_TITLES:
            if exclude in title:
                return False
        return True

    def _find_kakao_win(self) -> bool:
        """Windows에서 카카오톡 창 확인"""
        try:
            import win32gui

            def callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if self._is_kakao_window(title):
                        results.append(hwnd)

            results = []
            win32gui.EnumWindows(callback, results)
            return len(results) > 0
        except ImportError:
            try:
                import pygetwindow as gw
                windows = [w for w in gw.getWindowsWithTitle(self.KAKAO_WINDOW_TITLE_WIN)
                           if self._is_kakao_window(w.title)]
                return len(windows) > 0
            except Exception:
                return False

    def activate_kakao(self) -> bool:
        """카카오톡 창 활성화 (포커스)"""
        if self.system == "Darwin":
            return self._activate_kakao_mac()
        elif self.system == "Windows":
            return self._activate_kakao_win()
        return False

    def _activate_kakao_mac(self) -> bool:
        """Mac에서 카카오톡 활성화"""
        try:
            script = '''
            tell application "KakaoTalk"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", script], timeout=5)
            return True
        except Exception:
            return False

    def _activate_kakao_win(self) -> bool:
        """Windows에서 카카오톡 활성화"""
        try:
            import win32gui
            import win32con

            def callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if self._is_kakao_window(title):
                        results.append(hwnd)

            results = []
            win32gui.EnumWindows(callback, results)
            if results:
                hwnd = results[0]
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    # SetForegroundWindow 제한 우회: Alt키 트릭
                    import ctypes
                    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Alt down
                    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # Alt up
                    win32gui.SetForegroundWindow(hwnd)
                return True
            return False
        except ImportError:
            try:
                import pygetwindow as gw
                windows = [w for w in gw.getWindowsWithTitle(self.KAKAO_WINDOW_TITLE_WIN)
                           if self._is_kakao_window(w.title)]
                if windows:
                    windows[0].activate()
                    return True
            except Exception:
                pass
            return False

    def position_kakao_window(self) -> bool:
        """카카오톡 창을 계산된 위치로 이동 및 크기 조정"""
        if not self.kakao_rect:
            self.calculate_kakao_position()

        x = self.kakao_rect["x"]
        y = self.kakao_rect["y"]
        w = self.kakao_rect["width"]
        h = self.kakao_rect["height"]

        if self.system == "Darwin":
            return self._position_kakao_mac(x, y, w, h)
        elif self.system == "Windows":
            return self._position_kakao_win(x, y, w, h)
        return False

    def _position_kakao_mac(self, x, y, w, h) -> bool:
        """Mac에서 카카오톡 창 위치/크기 설정"""
        try:
            script = f'''
            tell application "System Events"
                tell process "KakaoTalk"
                    set frontmost to true
                    delay 0.3
                    try
                        set position of window 1 to {{{x}, {y}}}
                        set size of window 1 to {{{w}, {h}}}
                    end try
                end tell
            end tell
            '''
            subprocess.run(["osascript", "-e", script], timeout=10)
            return True
        except Exception as e:
            print(f"[WindowController] Mac position error: {e}")
            return False

    def _position_kakao_win(self, x, y, w, h) -> bool:
        """Windows에서 카카오톡 창 위치/크기 설정"""
        try:
            import win32gui
            import win32con

            def callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if self._is_kakao_window(title):
                        results.append(hwnd)

            results = []
            win32gui.EnumWindows(callback, results)
            if results:
                hwnd = results[0]
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.MoveWindow(hwnd, x, y, w, h, True)
                return True
            return False
        except ImportError:
            try:
                import pygetwindow as gw
                windows = [w_ for w_ in gw.getWindowsWithTitle(self.KAKAO_WINDOW_TITLE_WIN)
                           if self._is_kakao_window(w_.title)]
                if windows:
                    win = windows[0]
                    win.moveTo(x, y)
                    win.resizeTo(w, h)
                    return True
            except Exception:
                pass
            return False

    def calculate_ui_coordinates(self) -> dict:
        """
        카카오톡 창 실제 위치를 감지하여 UI 요소 절대좌표 자동 계산

        Windows 카카오톡 PC 기준 상대좌표 비율 (창 크기 대비):
        - 돋보기:    x=0.824, y=0.077   (우상단)
        - 검색입력:  x=0.336, y=0.151   (상단 중앙)
        - 검색결과:  x=0.350, y=0.260   (검색입력 아래)
        - 메시지입력: x=0.095, y=0.874  (하단 좌측)
        - 전송버튼:  x=0.860, y=0.973   (하단 우측)
        - 이미지전송: x=0.481, y=0.577  (중앙)
        - 뒤로가기:  x=0.957, y=0.027   (우상단 끝)
        """
        # 카카오톡 창 실제 위치 감지 시도
        current_rect = self._get_current_kakao_rect()
        if current_rect:
            self.kakao_rect = current_rect
        elif not self.kakao_rect:
            self.calculate_kakao_position()

        kx = self.kakao_rect["x"]
        ky = self.kakao_rect["y"]
        kw = self.kakao_rect["width"]
        kh = self.kakao_rect["height"]

        coords = {
            "search_icon": {
                "x": kx + int(kw * 0.824),
                "y": ky + int(kh * 0.077),
                "description": "돋보기 검색 아이콘 (우상단)"
            },
            "search_input": {
                "x": kx + int(kw * 0.336),
                "y": ky + int(kh * 0.151),
                "description": "검색 입력 필드 (검색 모드 진입 후)"
            },
            "first_result": {
                "x": kx + int(kw * 0.350),
                "y": ky + int(kh * 0.260),
                "description": "첫 번째 검색 결과"
            },
            "message_input": {
                "x": kx + int(kw * 0.095),
                "y": ky + int(kh * 0.874),
                "description": "메시지 입력창 (채팅방 하단)"
            },
            "send_enter": {
                "x": kx + int(kw * 0.860),
                "y": ky + int(kh * 0.973),
                "description": "보내기(전송) 버튼"
            },
            "image_send": {
                "x": kx + int(kw * 0.481),
                "y": ky + int(kh * 0.577),
                "description": "이미지 전송 확인 버튼"
            },
            "back_button": {
                "x": kx + int(kw * 0.957),
                "y": ky + int(kh * 0.027),
                "description": "뒤로가기/닫기 버튼 (우상단)"
            },
            "search_result_area": {
                "x1": kx + 10,
                "y1": ky + int(kh * 0.15),
                "x2": kx + kw - 10,
                "y2": ky + int(kh * 0.50),
                "description": "검색 결과 영역 (OCR 대상)"
            },
        }
        return coords

    def calibrate(self, screen_capture) -> dict:
        """
        스크린샷 기반 캘리브레이션
        카카오톡 창을 캡처하고 UI 요소 위치를 검증

        Returns:
            {
                "success": bool,
                "screenshot_path": str,
                "coordinates": dict,
                "kakao_rect": dict,
            }
        """
        if not self.kakao_rect:
            self.calculate_kakao_position()

        result = {
            "success": False,
            "screenshot_path": None,
            "coordinates": {},
            "kakao_rect": self.kakao_rect,
        }

        try:
            # 1. 카카오톡 창 캡처
            screenshot = screen_capture.capture_kakao_window(self.kakao_rect)
            screenshot_path = screen_capture.save_screenshot(screenshot, "calibration")
            result["screenshot_path"] = screenshot_path

            # 2. 좌표 계산
            coords = self.calculate_ui_coordinates()
            result["coordinates"] = coords

            # 3. 캘리브레이션 성공
            result["success"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def setup(self) -> dict:
        """
        전체 초기 설정 실행
        1. 화면 감지
        2. 카카오톡 찾기
        3. 활성화
        4. 위치/크기 고정
        5. UI 좌표 계산
        Returns: 설정 결과 딕셔너리
        """
        result = {
            "screen": self.get_screen_info(),
            "kakao_found": False,
            "kakao_positioned": False,
            "coordinates": {}
        }

        # 카카오톡 찾기
        result["kakao_found"] = self.find_kakao_window()
        if not result["kakao_found"]:
            return result

        # 활성화
        self.activate_kakao()

        # 위치 계산 및 이동
        self.calculate_kakao_position()
        result["kakao_positioned"] = self.position_kakao_window()

        # UI 좌표 계산
        result["coordinates"] = self.calculate_ui_coordinates()

        return result
