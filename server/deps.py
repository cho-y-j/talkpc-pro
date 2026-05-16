"""FastAPI 공통 의존성 — 인증된 사용자 추출."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db import get_db
from models import User
from security import decode_token

_bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """토큰 검증 + 사용자 조회. 상태 검증은 호출 측 책임 (heartbeat 가 별도 검증).

    토큰만 무효/없음이면 401. 사용자 존재 여부는 검증하되 상태는 통과.
    """
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰 없음")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰 무효")
    user = db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자 없음")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    """어드민 전용 엔드포인트 가드 — is_admin=True 만 통과."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "어드민 권한 필요")
    return user
