"""
PaddleOCR 한국어 OCR 공통 헬퍼.

★ 카톡 친구 OCR 95%+ 파이프라인 (CLAUDE.md "절대 변경 금지" 설정)
   - 5x Lanczos 확대
   - 회색조 → 대비 1.5x → UnsharpMask(2,150,3) → RGB 복원
   - PaddleOCR det_db_thresh=0.2, box_thresh=0.5, unclip=2.0

이 모듈은 kakao_friends.py 의 검증된 _get_paddle_ocr() 인스턴스를 그대로 재사용.
kakao_friends.py 는 변경 없음. 새 사용처(예: 검색결과 검증)는 이 헬퍼를 통해 사용.
"""

import re
from PIL import Image, ImageEnhance, ImageFilter

try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False


def get_paddle_ocr():
    """kakao_friends.py 의 lazy-init paddle 인스턴스 재사용.
    이미 초기화돼 있으면 그대로, 아니면 첫 호출에서 모델 로드.
    """
    try:
        from core.kakao_friends import _get_paddle_ocr
        return _get_paddle_ocr()
    except Exception:
        return None


def preprocess_for_paddle(image: "Image.Image") -> "Image.Image":
    """카톡 OCR 전처리 — 5x 확대 + 회색조 + 대비 + 샤프닝 + RGB 복원.

    ★ CLAUDE.md "절대 변경 금지" 검증된 파이프라인.
       사용자가 95% 정확도 검증하고 보존 명시함. 이 함수 수정 시 정확도 회귀 위험.
    """
    big = image.resize(
        (image.width * 5, image.height * 5),
        Image.LANCZOS,
    )
    gray = big.convert("L")
    contrasted = ImageEnhance.Contrast(gray).enhance(1.5)
    sharpened = contrasted.filter(
        ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)
    )
    return sharpened.convert("RGB")


def recognize_korean_text(image: "Image.Image") -> dict:
    """한국어 OCR — 텍스트 + 박스 정보 반환.

    Returns:
        {
            "text": str,                # 모든 박스 텍스트 합침 (위→아래, 좌→우)
            "boxes": [{"text", "conf", "y", "x"}, ...],
            "engine": "paddle" | "none",
        }
    """
    if not _NP_AVAILABLE:
        return {"text": "", "boxes": [], "engine": "none"}

    paddle = get_paddle_ocr()
    if paddle is None:
        return {"text": "", "boxes": [], "engine": "none"}

    pre = preprocess_for_paddle(image)
    arr = np.array(pre)
    try:
        result = paddle.ocr(arr, cls=False)
    except Exception:
        return {"text": "", "boxes": [], "engine": "paddle"}

    if not result or not result[0]:
        return {"text": "", "boxes": [], "engine": "paddle"}

    items = []
    for entry in result[0]:
        try:
            box, (text, conf) = entry
        except (ValueError, TypeError):
            continue
        if not text or conf < 0.5:
            continue
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        items.append({
            "text": text.strip(),
            "conf": float(conf),
            "y": float(min(ys)),
            "x": float(min(xs)),
        })

    items.sort(key=lambda i: (i["y"], i["x"]))
    joined = " ".join(it["text"] for it in items)
    return {"text": joined, "boxes": items, "engine": "paddle"}


def verify_name_match(image: "Image.Image", target_name: str,
                       tolerance: int = 1) -> dict:
    """검색 결과 이미지에서 target_name 매칭 검증.

    CLAUDE.md 명시 4단계 (95% 검증된 파이프라인) — 변경 금지:
      1) exact        — 이름 박스 == target
      2) contain      — 이름 박스가 target 포함 또는 그 반대
      3) text_contain — 전체 OCR 텍스트에 target 정확 포함
      4) fuzzy        — 1글자 차이 슬라이딩 윈도우 (OCR 글자 오인식 보정)

    Args:
        target_name: 검색 입력 이름
        tolerance: 허용 오차 글자 수 (기본 1자)

    Returns:
        {
            "matched": bool,
            "ocr_text": str,           # 전체 OCR 텍스트
            "ocr_name": str,           # 추출된 이름 (가장 위 박스)
            "confidence": float,
            "engine": str,
            "match_level": "exact"|"contain"|"text_contain"|"fuzzy"|"none",
        }
    """
    res = recognize_korean_text(image)
    if not res["boxes"]:
        return {
            "matched": False, "ocr_text": "", "ocr_name": "",
            "confidence": 0.0, "engine": res["engine"],
            "match_level": "none",
        }

    # ★ 한글 포함 박스 우선 — ":" 같은 특수문자 박스가 첫 번째로 잡혀
    #   이름이 무시되는 버그 방지.
    name_boxes = [b for b in res["boxes"]
                   if re.search(r"[가-힣]", b["text"])]
    top_box = name_boxes[0] if name_boxes else res["boxes"][0]
    ocr_name = top_box["text"]

    target_clean = re.sub(r"\s+", "", (target_name or "").strip())
    ocr_clean = re.sub(r"\s+", "", ocr_name)
    # 전체 OCR 텍스트 (모든 박스 합쳐진 것) — text_contain 매칭용
    ocr_text_clean = re.sub(r"\s+", "", res["text"])

    if not target_clean:
        return {
            "matched": False, "ocr_text": res["text"], "ocr_name": ocr_name,
            "confidence": top_box["conf"], "engine": res["engine"],
            "match_level": "none",
        }

    # 1) 정확 일치 (이름 박스)
    if target_clean == ocr_clean:
        return {
            "matched": True, "ocr_text": res["text"], "ocr_name": ocr_name,
            "confidence": top_box["conf"], "engine": res["engine"],
            "match_level": "exact",
        }

    # 2) 부분 포함 (이름 박스 내)
    if ocr_clean and (target_clean in ocr_clean or ocr_clean in target_clean):
        return {
            "matched": True, "ocr_text": res["text"], "ocr_name": ocr_name,
            "confidence": top_box["conf"], "engine": res["engine"],
            "match_level": "contain",
        }

    # 3) ★ 전체 OCR 텍스트에 포함 — 다른 박스들 합친 텍스트에서 찾기
    #    예: ocr_text=": 안덕현" 일 때 target="안덕현" 매칭됨
    if target_clean in ocr_text_clean:
        return {
            "matched": True, "ocr_text": res["text"], "ocr_name": ocr_name,
            "confidence": top_box["conf"], "engine": res["engine"],
            "match_level": "text_contain",
        }

    # 4) 한글 글자 단위 fuzzy (tolerance 자 차이 허용) — OCR 1글자 오인식 보정
    target_hangul = re.findall(r"[가-힣]", target_clean)
    text_hangul = re.findall(r"[가-힣]", ocr_text_clean)
    if target_hangul and text_hangul:
        target_len = len(target_hangul)
        for i in range(len(text_hangul) - target_len + 1):
            window = text_hangul[i:i + target_len]
            diff = sum(1 for a, b in zip(target_hangul, window) if a != b)
            if diff <= tolerance:
                return {
                    "matched": True, "ocr_text": res["text"],
                    "ocr_name": ocr_name, "confidence": top_box["conf"],
                    "engine": res["engine"], "match_level": "fuzzy",
                }

    return {
        "matched": False, "ocr_text": res["text"], "ocr_name": ocr_name,
        "confidence": top_box["conf"], "engine": res["engine"],
        "match_level": "none",
    }
