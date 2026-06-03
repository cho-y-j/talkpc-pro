"""환경 설정 — Pydantic Settings 로 .env 자동 로드."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    DATABASE_URL: str
    JWT_SECRET: str
    # JWT 만료 — 분 단위. 기본 30일 (43200분). 매일 어드민/클라이언트 재로그인
    # 불편 해소. 라이선스/디바이스 한도 등 보호 로직은 heartbeat(3분 주기) 가
    # 별도로 status/expires_at 재검증하므로 JWT 수명이 길어도 안전.
    JWT_EXPIRES_MIN: int = 43200
    DEVICES_PER_USER: int = 1


settings = Settings()
