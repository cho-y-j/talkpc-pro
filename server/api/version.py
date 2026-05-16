"""/version — 클라이언트 버전 체크 + 강제 업데이트 안내.

ENV:
  LATEST_VERSION       최신 출시 버전 (예: 1.0.2)
  MIN_REQUIRED_VERSION 이보다 낮은 클라는 강제 업데이트 (예: 1.0.0)
  DOWNLOAD_URL         최신 인스톨러/zip URL (GitHub Releases)
  RELEASE_NOTES        한 줄 변경사항 (선택)
"""
import os
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(tags=["version"])


class VersionResponse(BaseModel):
    latest: str
    min_required: str
    download_url: str
    release_notes: str = ""
    # 클라가 보낸 current 버전과 비교한 결과
    is_outdated: bool = False        # current < latest
    requires_update: bool = False    # current < min_required (강제)


def _parse_semver(v: str) -> tuple:
    """1.0.2 → (1, 0, 2). 잘못된 형식은 (0,0,0)."""
    try:
        parts = v.replace("v", "").split(".")
        return tuple(int(p) for p in parts[:3]) + (0,) * (3 - len(parts))
    except Exception:
        return (0, 0, 0)


@router.get("/version", response_model=VersionResponse)
def version(current: str = Query("0.0.0", description="클라이언트 현재 버전")):
    latest = os.environ.get("LATEST_VERSION", "0.1.0")
    min_required = os.environ.get("MIN_REQUIRED_VERSION", "0.1.0")
    download_url = os.environ.get(
        "DOWNLOAD_URL",
        "https://github.com/cho-y-j/talkpc-pro/releases/latest",
    )
    notes = os.environ.get("RELEASE_NOTES", "")

    cur = _parse_semver(current)
    return VersionResponse(
        latest=latest,
        min_required=min_required,
        download_url=download_url,
        release_notes=notes,
        is_outdated=cur < _parse_semver(latest),
        requires_update=cur < _parse_semver(min_required),
    )
