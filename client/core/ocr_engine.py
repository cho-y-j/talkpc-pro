"""
OCREngine - Tesseract OCR 모듈
검색 결과 텍스트 인식 및 이름 매칭
"""

try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance
except ImportError:
    pytesseract = None
    Image = None


class OCREngine:
    """Tesseract 기반 OCR 엔진"""

    def __init__(self, language: str = "kor+eng", confidence_threshold: int = 70):
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.available = False
        self.tessdata_dir = None
        self._check_tesseract()

    def _check_tesseract(self):
        """Tesseract 설치 확인 + 프로젝트 내 tessdata 우선 사용"""
        if pytesseract is None:
            return

        import platform
        import os

        # Windows: 설치 경로 설정
        if platform.system() == "Windows":
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # 프로젝트 내 tessdata 확인 (exe와 스크립트 모두 지원)
        import sys
        if getattr(sys, 'frozen', False):
            # exe: exe 옆 config/tessdata 또는 _internal/config/tessdata
            exe_dir = os.path.dirname(sys.executable)
            candidates = [
                os.path.join(exe_dir, "config", "tessdata"),
                os.path.join(getattr(sys, '_MEIPASS', ''), "config", "tessdata"),
                os.path.join(exe_dir, "_internal", "config", "tessdata"),
            ]
        else:
            candidates = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "tessdata")
            ]

        for path in candidates:
            if os.path.exists(os.path.join(path, "kor.traineddata")):
                self.tessdata_dir = path
                break

        try:
            pytesseract.get_tesseract_version()
            self.available = True
        except Exception:
            self.available = False

    def _get_config(self, psm: int) -> str:
        """Tesseract config 문자열 생성 (tessdata 경로 포함)"""
        config = f"--psm {psm}"
        if self.tessdata_dir:
            # 경로를 슬래시로 변환 (Windows 백슬래시 문제 방지)
            td = self.tessdata_dir.replace("\\", "/")
            config += f" --tessdata-dir {td}"
        return config

    def preprocess_image(self, image: "Image.Image") -> "Image.Image":
        """OCR 정확도 향상을 위한 이미지 전처리 (다크모드 대응)"""
        # 그레이스케일 변환
        gray = image.convert("L")

        # 다크모드 감지: 평균 밝기가 낮으면 반전
        from PIL import ImageOps, ImageStat
        avg_brightness = ImageStat.Stat(gray).mean[0]
        if avg_brightness < 128:
            gray = ImageOps.invert(gray)

        # 대비 향상
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)

        # 샤프닝
        sharpened = enhanced.filter(ImageFilter.SHARPEN)

        # 3배 확대 (OCR 정확도 향상)
        width, height = sharpened.size
        resized = sharpened.resize((width * 3, height * 3), Image.LANCZOS)

        # 이진화 (흑백 분리 - 텍스트 선명도 극대화)
        threshold = 180
        resized = resized.point(lambda p: 255 if p > threshold else 0)

        return resized

    def extract_text(self, image: "Image.Image", preprocess: bool = True) -> str:
        """이미지에서 텍스트 추출 - 여러 PSM 모드 시도"""
        if not self.available:
            return ""

        if preprocess:
            image = self.preprocess_image(image)

        # 여러 PSM 모드로 시도하여 가장 많은 텍스트를 추출
        best_text = ""
        for psm in [11, 3, 6]:  # sparse → auto → uniform block
            try:
                text = pytesseract.image_to_string(
                    image,
                    lang=self.language,
                    config=self._get_config(psm)
                ).strip()
                if len(text) > len(best_text):
                    best_text = text
            except Exception:
                continue
        return best_text

    def extract_text_with_data(self, image: "Image.Image", preprocess: bool = True) -> list:
        """텍스트와 위치/신뢰도 정보 함께 추출"""
        if not self.available:
            return []

        if preprocess:
            image = self.preprocess_image(image)

        all_results = []
        # 여러 PSM 모드로 시도
        for psm in [11, 3, 6]:
            try:
                data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    config=self._get_config(psm),
                    output_type=pytesseract.Output.DICT
                )

                n = len(data["text"])
                for i in range(n):
                    text = data["text"][i].strip()
                    conf = int(data["conf"][i])
                    if text and conf >= self.confidence_threshold:
                        # 중복 방지
                        if not any(r["text"] == text for r in all_results):
                            all_results.append({
                                "text": text,
                                "confidence": conf,
                                "x": data["left"][i],
                                "y": data["top"][i],
                                "width": data["width"][i],
                                "height": data["height"][i]
                            })
            except Exception:
                continue
        return all_results

    def verify_name_in_results(self, image: "Image.Image", target_name: str) -> dict:
        """
        검색 결과 이미지에서 대상 이름이 있는지 확인
        좁은 영역(이름 텍스트만)을 캡처했으므로 PSM 7(단일라인) 우선 사용
        신뢰도 기준을 낮춰서 한글 인식률 향상
        """
        if not self.available:
            return {
                "found": False,
                "matched_text": None,
                "confidence": 0,
                "position": None,
                "error": "Tesseract OCR이 설치되지 않았습니다."
            }

        preprocessed = self.preprocess_image(image)

        # 1단계: PSM 7(단일라인) → 13(raw) → 6(블록) 순으로 시도
        all_extracted = []
        for psm in [7, 13, 6, 3]:
            try:
                text = pytesseract.image_to_string(
                    preprocessed,
                    lang=self.language,
                    config=self._get_config(psm)
                ).strip()
                if text:
                    all_extracted.append(text)
                    # 완전 매칭
                    if target_name in text or text in target_name:
                        return {
                            "found": True,
                            "matched_text": text,
                            "confidence": 90,
                            "position": None
                        }
            except Exception:
                continue

        # 2단계: 전체 추출 텍스트에서 부분 매칭
        combined = " ".join(all_extracted)
        # 공백/특수문자 제거 후 비교
        clean_combined = combined.replace(" ", "").replace("\n", "")
        clean_target = target_name.replace(" ", "")

        if clean_target in clean_combined:
            return {
                "found": True,
                "matched_text": combined[:30],
                "confidence": 70,
                "position": None
            }

        # ❌ 3단계 (글자 집합 매칭) 제거 — false positive 의 주범.
        #    "안덕현" 검색 시 OCR 노이즈가 {안,현} 만 뽑아도 50% 매칭 통과 → 잘못된 사람 발송 위험.
        #    이름은 DB 에서 그대로 가져온 정확값이므로 부분 set 매칭 불필요.

        # 4단계: 저신뢰도 단어 결합 후 정확 contain 만 통과
        for psm in [7, 6]:
            try:
                data = pytesseract.image_to_data(
                    preprocessed,
                    lang=self.language,
                    config=self._get_config(psm),
                    output_type=pytesseract.Output.DICT
                )
                words = [t.strip() for t in data["text"] if t.strip()]
                word_text = "".join(words)
                if clean_target in word_text:
                    return {
                        "found": True,
                        "matched_text": word_text[:30],
                        "confidence": 30,
                        "position": None,
                        "low_confidence": True
                    }
            except Exception:
                continue

        return {
            "found": False,
            "matched_text": None,
            "confidence": 0,
            "position": None,
            "extracted_text": combined[:100] if combined else ""
        }
