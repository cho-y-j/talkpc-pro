"""인증 헬퍼 — 비밀번호 해시, JWT 발행/검증, 라이선스 키 생성."""
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from config import settings


def _to_bytes(plain: str) -> bytes:
    # bcrypt 는 72바이트 제한 — 초과 시 truncate (passlib 4.x 호환성 회피).
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bytes(plain), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode())
    except Exception:
        return False


def generate_license_key() -> str:
    """예: TPRO-7H3K-9XQ2-MN4P-AB8R (16자 + 하이픈)"""
    alphabet = string.ascii_uppercase + string.digits
    chunks = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "TPRO-" + "-".join(chunks)


def create_access_token(user_id: str, license_key: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRES_MIN)
    payload = {"sub": user_id, "lic": license_key, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return None
