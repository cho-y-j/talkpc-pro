"""
KakaoWin32 - Win32 API 기반 카카오톡 제어 엔진

핵심 원리:
- PostMessage로 클릭/키 이벤트를 윈도우에 직접 전달
- 물리적 마우스 이동이 발생하지 않아 자동화 탐지 회피
- 클립보드 + 붙여넣기로 한글 텍스트 입력
- WindowFromPoint로 자식 윈도우 자동 탐색 + 좌표 변환
"""

import time
import random
import ctypes
import ctypes.wintypes as wintypes
import tempfile
from pathlib import Path

try:
    import win32gui
    import win32api
    import win32con
    import win32clipboard
except ImportError:
    win32gui = None

user32 = ctypes.windll.user32

_LOG_PATH = Path(tempfile.gettempdir()) / "kakao_win32_debug.log"


def _log(msg):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _makelparam(x, y):
    """좌표를 LPARAM으로 패킹 (부호 처리)"""
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


class KakaoWin32:
    """
    Win32 API 카카오톡 제어 엔진

    모든 UI 조작을 PostMessage/SendMessage로 처리하여
    물리적 마우스 커서 이동이 전혀 발생하지 않음
    """

    EXCLUDE_TITLES = ["TalkPC", "Auto Messenger", "자동 발송"]

    # 클릭 모드
    MODE_POSTMESSAGE = "postmessage"   # PostMessage (커서 이동 없음, 권장)
    MODE_STEALTH = "stealth"           # 커서 숨김 + 빠른 이동/클릭/복원

    def __init__(self, click_mode=None):
        if not win32gui:
            raise ImportError("pywin32가 설치되지 않았습니다.")
        self.main_hwnd = None
        self.chat_hwnd = None
        self.click_mode = click_mode or self.MODE_POSTMESSAGE

    # ── 윈도우 탐색 ──

    def find_main_window(self):
        """카카오톡 메인 창 핸들 찾기"""
        results = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title == "카카오톡":
                    for ex in self.EXCLUDE_TITLES:
                        if ex in title:
                            return True
                    results.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)

        if results:
            self.main_hwnd = results[0]
            _log(f"메인 창 발견: hwnd={self.main_hwnd}")
            return self.main_hwnd

        _log("메인 창을 찾을 수 없음")
        return None

    def get_foreground_as_chat(self):
        """현재 포그라운드 창을 채팅창으로 설정"""
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value

        for ex in self.EXCLUDE_TITLES:
            if ex in title:
                return None

        self.chat_hwnd = hwnd
        _log(f"채팅창 감지: hwnd={hwnd} title='{title}'")
        return hwnd

    def get_window_rect(self, hwnd=None):
        """윈도우 위치/크기 {x, y, width, height}"""
        hwnd = hwnd or self.main_hwnd
        if not hwnd:
            return None
        rect = win32gui.GetWindowRect(hwnd)
        return {
            "x": rect[0], "y": rect[1],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1]
        }

    def activate(self, hwnd=None):
        """창 활성화 (포커스)"""
        hwnd = hwnd or self.main_hwnd
        if not hwnd:
            return False

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # Alt 키 트릭: SetForegroundWindow 제한 우회
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, 2, 0)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
        time.sleep(0.3)
        return True

    # ── 좌표 변환 ──

    def _abs_to_target(self, abs_x, abs_y):
        """
        절대 스크린 좌표 → (타겟 윈도우 핸들, 클라이언트 좌표)
        WindowFromPoint로 해당 좌표의 실제 윈도우를 자동 탐색
        """
        pt = wintypes.POINT(abs_x, abs_y)
        target = user32.WindowFromPoint(pt)

        if not target:
            target = self.main_hwnd
            _log(f"WindowFromPoint 실패, main_hwnd 사용")

        # 스크린 → 클라이언트 좌표 변환
        user32.ScreenToClient(target, ctypes.byref(pt))
        return target, pt.x, pt.y

    # ── 클릭 ──

    def click(self, abs_x, abs_y):
        """
        절대 좌표 클릭 (마우스 커서 이동 없음)
        click_mode에 따라 PostMessage 또는 Stealth 모드 사용
        """
        if self.click_mode == self.MODE_STEALTH:
            self._stealth_click(abs_x, abs_y)
        else:
            self._post_click(abs_x, abs_y)

    def double_click(self, abs_x, abs_y):
        """더블클릭 (마우스 커서 이동 없음)"""
        if self.click_mode == self.MODE_STEALTH:
            self._stealth_double_click(abs_x, abs_y)
        else:
            self._post_double_click(abs_x, abs_y)

    # ── PostMessage 클릭 (완전 무커서) ──

    def _post_click(self, abs_x, abs_y):
        """PostMessage 단일 클릭"""
        target, cx, cy = self._abs_to_target(abs_x, abs_y)
        lparam = _makelparam(cx, cy)

        _log(f"PostMessage 클릭: abs({abs_x},{abs_y}) → hwnd={target} client({cx},{cy})")

        win32api.PostMessage(target, win32con.WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.02)
        win32api.PostMessage(target, win32con.WM_LBUTTONDOWN,
                             win32con.MK_LBUTTON, lparam)
        time.sleep(random.uniform(0.03, 0.08))
        win32api.PostMessage(target, win32con.WM_LBUTTONUP, 0, lparam)

    def _post_double_click(self, abs_x, abs_y):
        """PostMessage 더블클릭"""
        target, cx, cy = self._abs_to_target(abs_x, abs_y)
        lparam = _makelparam(cx, cy)

        _log(f"PostMessage 더블클릭: abs({abs_x},{abs_y}) → hwnd={target} client({cx},{cy})")

        # 첫 번째 클릭
        win32api.PostMessage(target, win32con.WM_LBUTTONDOWN,
                             win32con.MK_LBUTTON, lparam)
        time.sleep(0.02)
        win32api.PostMessage(target, win32con.WM_LBUTTONUP, 0, lparam)
        time.sleep(0.05)

        # 더블클릭 이벤트
        win32api.PostMessage(target, win32con.WM_LBUTTONDBLCLK,
                             win32con.MK_LBUTTON, lparam)
        time.sleep(0.02)
        win32api.PostMessage(target, win32con.WM_LBUTTONUP, 0, lparam)

    # ── Stealth 클릭 (커서 숨김 + 빠른 이동/복원) ──

    def _stealth_click(self, abs_x, abs_y):
        """커서 위치 저장 → 숨김 → 이동+클릭 → 복원 → 보이기"""
        saved = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(saved))

        _log(f"Stealth 클릭: ({abs_x},{abs_y}) 원래위치({saved.x},{saved.y})")

        # 커서 숨기기
        user32.ShowCursor(False)
        try:
            user32.SetCursorPos(abs_x, abs_y)
            time.sleep(0.01)
            user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
            time.sleep(random.uniform(0.03, 0.07))
            user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
            time.sleep(0.01)
        finally:
            # 원래 위치로 복원 + 커서 보이기
            user32.SetCursorPos(saved.x, saved.y)
            user32.ShowCursor(True)

    def _stealth_double_click(self, abs_x, abs_y):
        """Stealth 더블클릭"""
        saved = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(saved))

        _log(f"Stealth 더블클릭: ({abs_x},{abs_y})")

        user32.ShowCursor(False)
        try:
            user32.SetCursorPos(abs_x, abs_y)
            time.sleep(0.01)
            # 첫 번째 클릭
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.05)
            # 두 번째 클릭
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.01)
        finally:
            user32.SetCursorPos(saved.x, saved.y)
            user32.ShowCursor(True)

    # ── 키보드 (PostMessage) ──

    def press_key(self, hwnd, vk_code):
        """키 입력 (PostMessage - 포커스된 컨트롤에 전달)"""
        scan = user32.MapVirtualKeyW(vk_code, 0)
        lparam_down = 1 | (scan << 16)
        lparam_up = 1 | (scan << 16) | (1 << 30) | (1 << 31)

        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lparam_down)
        time.sleep(0.05)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lparam_up)

    def press_enter(self, hwnd=None):
        """Enter 키"""
        hwnd = hwnd or self.chat_hwnd or self.main_hwnd
        self.press_key(hwnd, win32con.VK_RETURN)

    def press_escape(self, hwnd=None):
        """Escape 키"""
        hwnd = hwnd or self.main_hwnd
        self.press_key(hwnd, win32con.VK_ESCAPE)

    # ── 텍스트 입력 ──

    def paste_text(self, text):
        """
        텍스트 입력: 클립보드 복사 → Ctrl+V
        호출 전에 카카오톡이 포그라운드 상태여야 함 (sender에서 activate 호출)
        """
        # 1. 클립보드에 복사
        for retry in range(3):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                break
            except Exception as e:
                _log(f"클립보드 복사 재시도 {retry+1}: {e}")
                time.sleep(0.1)
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass

        time.sleep(0.15)

        # 2. Ctrl+V (카카오톡이 포그라운드 상태)
        user32.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(ord('V'), 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(ord('V'), 0, 2, 0)   # KEYEVENTF_KEYUP = 2
        time.sleep(0.03)
        user32.keybd_event(win32con.VK_CONTROL, 0, 2, 0)
        time.sleep(0.3)

        _log(f"paste_text 완료: '{text[:30]}...'")

    def clear_input(self, hwnd=None):
        """입력 필드 전체 삭제: Home → Shift+End → Delete"""
        hwnd = hwnd or self.main_hwnd

        # Home
        self.press_key(hwnd, win32con.VK_HOME)
        time.sleep(0.1)

        # Shift+End (전체 선택)
        scan_shift = user32.MapVirtualKeyW(win32con.VK_SHIFT, 0)
        scan_end = user32.MapVirtualKeyW(win32con.VK_END, 0)

        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_SHIFT,
                             1 | (scan_shift << 16))
        time.sleep(0.03)
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_END,
                             1 | (scan_end << 16))
        time.sleep(0.03)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_END,
                             1 | (scan_end << 16) | (1 << 30) | (1 << 31))
        time.sleep(0.03)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_SHIFT,
                             1 | (scan_shift << 16) | (1 << 30) | (1 << 31))
        time.sleep(0.1)

        # Delete
        self.press_key(hwnd, win32con.VK_DELETE)
        time.sleep(0.2)

        _log("clear_input 완료")

    # ── 이미지 ──

    def paste_image(self, image_path):
        """이미지 클립보드 복사 → Ctrl+V"""
        from core.image_clipboard import copy_image_to_clipboard
        copy_image_to_clipboard(image_path)
        time.sleep(0.3)

        user32.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(ord('V'), 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(ord('V'), 0, 2, 0)
        time.sleep(0.03)
        user32.keybd_event(win32con.VK_CONTROL, 0, 2, 0)

        _log(f"paste_image 완료: {image_path}")

    # ── 창 관리 ──

    def move_window(self, hwnd, x, y, w, h):
        """창 이동/크기 조정"""
        win32gui.MoveWindow(hwnd, x, y, w, h, True)

    def position_chat_to_main(self):
        """채팅창을 메인 카카오톡 창 위치로 이동"""
        if not self.main_hwnd or not self.chat_hwnd:
            return
        if self.chat_hwnd == self.main_hwnd:
            return

        rect = self.get_window_rect(self.main_hwnd)
        if rect:
            self.move_window(
                self.chat_hwnd,
                rect["x"], rect["y"], rect["width"], rect["height"]
            )
            _log(f"채팅창 배치: ({rect['x']},{rect['y']}) {rect['width']}x{rect['height']}")
            time.sleep(0.3)

    # ── 디버그 ──

    def enum_children(self, hwnd=None):
        """자식 윈도우 목록 (디버그/분석용)"""
        hwnd = hwnd or self.main_hwnd
        children = []

        def callback(child, _):
            cls = win32gui.GetClassName(child)
            title = win32gui.GetWindowText(child)
            rect = win32gui.GetWindowRect(child)
            vis = win32gui.IsWindowVisible(child)
            children.append({
                "hwnd": child,
                "class": cls,
                "title": title,
                "rect": rect,
                "visible": bool(vis)
            })
            return True

        win32gui.EnumChildWindows(hwnd, callback, None)
        return children
