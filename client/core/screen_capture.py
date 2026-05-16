"""
ScreenCapture - 스크린샷 모듈
카카오톡 창 및 특정 영역 캡처
"""

import time
from pathlib import Path

try:
    from PIL import Image, ImageGrab
except ImportError:
    Image = None
    ImageGrab = None

try:
    import pyautogui
except ImportError:
    pyautogui = None


class ScreenCapture:
    """화면 캡처 모듈"""

    def __init__(self, save_dir: str = None):
        self.save_dir = Path(save_dir) if save_dir else Path("./logs/screenshots")
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def capture_full_screen(self) -> "Image.Image":
        """전체 화면 캡처"""
        if pyautogui:
            return pyautogui.screenshot()
        elif ImageGrab:
            return ImageGrab.grab()
        raise RuntimeError("스크린샷 라이브러리를 찾을 수 없습니다.")

    def capture_region(self, x1: int, y1: int, x2: int, y2: int) -> "Image.Image":
        """특정 영역 캡처"""
        if pyautogui:
            width = x2 - x1
            height = y2 - y1
            return pyautogui.screenshot(region=(x1, y1, width, height))
        elif ImageGrab:
            return ImageGrab.grab(bbox=(x1, y1, x2, y2))
        raise RuntimeError("스크린샷 라이브러리를 찾을 수 없습니다.")

    def capture_kakao_window(self, kakao_rect: dict) -> "Image.Image":
        """카카오톡 창 전체 캡처"""
        x = kakao_rect["x"]
        y = kakao_rect["y"]
        w = kakao_rect["width"]
        h = kakao_rect["height"]
        return self.capture_region(x, y, x + w, y + h)

    def capture_search_results(self, coordinates: dict) -> "Image.Image":
        """검색 결과 영역만 캡처 (OCR용)"""
        area = coordinates.get("search_result_area", {})
        if not area:
            raise ValueError("검색 결과 영역 좌표가 없습니다.")
        return self.capture_region(
            area["x1"], area["y1"],
            area["x2"], area["y2"]
        )

    def save_screenshot(self, image: "Image.Image", name: str = None) -> str:
        """스크린샷 파일로 저장"""
        if name is None:
            name = f"capture_{int(time.time())}"
        filepath = self.save_dir / f"{name}.png"
        image.save(str(filepath))
        return str(filepath)
