from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Env
    ENVIRONMENT: str = "dev"
    DEBUG: bool = True

    # Allowed Hosts
    ALLOWED_HOSTS: List[str] = []
    CORS_ALLOWED_ORIGINS: List[str] = []

    # URL Constants
    API_V1_STR: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    # Secret
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"

    # Authentication
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # Token Expiration
    REFRESH_TOKEN_EXPIRES_DAYS: int = 7
    ACCESS_TOKEN_EXPIRES_MINUTES: int = 300
    PASSWORD_RESET_CODE_EXPIRE_MINUTES: int = 15

    # Email Credentials
    MAIL_USERNAME: str = "test"
    MAIL_PASSWORD: str = "test"
    MAIL_FROM: str = "test@email.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "test"
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = True
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
