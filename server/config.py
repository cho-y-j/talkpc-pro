"""환경 설정 — Pydantic Settings 로 .env 자동 로드."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRES_MIN: int = 1440
    DEVICES_PER_USER: int = 1


settings = Settings()
