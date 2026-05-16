"""
MessageEngine - 메시지 템플릿 및 변수 치환 엔진
%이름%, %회사% 등 변수를 실제 값으로 치환
"""

import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


class MessageTemplate:
    """메시지 템플릿 데이터 클래스 (여러 변형 지원)"""

    def __init__(self, name: str, content: str, category: str = "all",
                 template_id: str = None, image_path: str = "",
                 contents: list = None):
        self.id = template_id or f"tmpl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.name = name
        # contents: 여러 변형 메시지 리스트
        if contents:
            self.contents = contents
        else:
            self.contents = [content] if content else [""]
        self.category = category
        self.image_path = image_path
        self.created_at = datetime.now().isoformat()

    @property
    def content(self) -> str:
        """첫 번째 변형 반환 (하위 호환)"""
        return self.contents[0] if self.contents else ""

    @content.setter
    def content(self, value: str):
        """첫 번째 변형 설정 (하위 호환)"""
        if self.contents:
            self.contents[0] = value
        else:
            self.contents = [value]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,       # 하위 호환
            "contents": self.contents,     # 여러 변형
            "category": self.category,
            "image_path": self.image_path,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MessageTemplate":
        # contents가 있으면 사용, 없으면 content에서 단일 리스트 생성
        contents = data.get("contents")
        if not contents:
            contents = [data.get("content", "")]
        tmpl = cls(
            name=data["name"],
            content="",
            category=data.get("category", "all"),
            template_id=data.get("id"),
            image_path=data.get("image_path", ""),
            contents=contents
        )
        tmpl.created_at = data.get("created_at", tmpl.created_at)
        return tmpl


class MessageEngine:
    """메시지 템플릿 관리 및 변수 치환"""

    # 지원 변수 목록
    VARIABLES = {
        "%이름%": "name",
        "%카테고리%": "category",
        "%회사%": "company",
        "%직급%": "position",
        "%전화번호%": "phone",
        "%메모%": "memo",
        "%생일%": "birthday",
        "%기념일%": "anniversary",
        "%날짜%": "_date",
        "%요일%": "_weekday",
    }

    WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

    def __init__(self, template_dir: str = None):
        self.template_dir = Path(template_dir) if template_dir else Path("./data/templates")
        self.templates: list[MessageTemplate] = []
        self.load_templates()

    def load_templates(self):
        """저장된 템플릿 로드"""
        self.templates = []
        if not self.template_dir.exists():
            self.template_dir.mkdir(parents=True, exist_ok=True)
            return

        for fp in self.template_dir.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for t in data.get("templates", []):
                    self.templates.append(MessageTemplate.from_dict(t))
            except Exception:
                continue

    def save_templates(self):
        """템플릿 저장"""
        self.template_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "templates": [t.to_dict() for t in self.templates]
        }
        filepath = self.template_dir / "custom.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_template(self, name: str, content: str, category: str = "all",
                     image_path: str = "") -> MessageTemplate:
        """새 템플릿 추가"""
        tmpl = MessageTemplate(name=name, content=content, category=category,
                               image_path=image_path)
        self.templates.append(tmpl)
        self.save_templates()
        return tmpl

    def update_template(self, template_id: str, **kwargs) -> bool:
        """템플릿 수정"""
        for t in self.templates:
            if t.id == template_id:
                for key, value in kwargs.items():
                    if hasattr(t, key):
                        setattr(t, key, value)
                self.save_templates()
                return True
        return False

    def delete_template(self, template_id: str) -> bool:
        """템플릿 삭제"""
        before = len(self.templates)
        self.templates = [t for t in self.templates if t.id != template_id]
        if len(self.templates) < before:
            self.save_templates()
            return True
        return False

    def get_templates(self, category: str = None) -> list[MessageTemplate]:
        """템플릿 조회"""
        if category is None or category == "all":
            return self.templates
        return [t for t in self.templates if t.category in (category, "all")]

    def get_template_by_id(self, template_id: str) -> Optional[MessageTemplate]:
        """ID로 템플릿 조회"""
        for t in self.templates:
            if t.id == template_id:
                return t
        return None

    def extract_variables(self, text: str) -> list[str]:
        """텍스트에서 사용된 변수 목록 추출"""
        pattern = r"%[^%]+%"
        return re.findall(pattern, text)

    def substitute(self, template_content: str, contact_data: dict) -> str:
        """
        템플릿 변수를 실제 값으로 치환

        Args:
            template_content: "안녕하세요 %이름%님! %회사% 관련..."
            contact_data: {"name": "김철수", "company": "ABC건설", ...}

        Returns:
            "안녕하세요 김철수님! ABC건설 관련..."
        """
        result = template_content

        for var, field in self.VARIABLES.items():
            if var in result:
                if field == "_date":
                    value = datetime.now().strftime("%Y년 %m월 %d일")
                elif field == "_weekday":
                    value = self.WEEKDAYS[datetime.now().weekday()]
                else:
                    value = contact_data.get(field, "")
                result = result.replace(var, value)

        # 사용되지 않은 변수 제거 (빈 문자열로)
        result = re.sub(r"%[^%]+%", "", result)

        # 연속 공백 정리
        result = re.sub(r"  +", " ", result).strip()

        return result

    def substitute_random(self, contents: list, contact_data: dict) -> str:
        """여러 변형 중 랜덤 선택 후 변수 치환"""
        if not contents:
            return ""
        chosen = random.choice(contents)
        return self.substitute(chosen, contact_data)

    def generate_preview(self, template_content: str, contact_data: dict) -> str:
        """미리보기 생성 (치환 결과 반환)"""
        return self.substitute(template_content, contact_data)

    def batch_generate(self, template_content: str, contacts_data: list[dict]) -> list[dict]:
        """
        여러 연락처에 대해 일괄 메시지 생성

        Returns:
            [{"contact_name": "김철수", "message": "안녕하세요 김철수님...", ...}]
        """
        results = []
        for contact in contacts_data:
            message = self.substitute(template_content, contact)
            results.append({
                "contact_name": contact.get("name", ""),
                "contact_id": contact.get("id", ""),
                "message": message
            })
        return results
