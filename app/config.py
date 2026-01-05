from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_google_genai import ChatGoogleGenerativeAI

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Infrastructure & Environment ---
    ENVIRONMENT: str = Field(
        default="dev",
        pattern="^(dev|staging|prod)$",
        description="Deployment environment filter"
    )
    DEBUG: bool = Field(default=True)

    # --- Security & Database (Strictly Required) ---
    # Using Field(...) ensures the app fails fast if these are missing in prod
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = Field(default="HS256")
    
    DATABASE_URL: str = Field(...)
    TEST_DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./test.db")

    # --- Networking & CORS ---
    # Using AliasChoices allows flexibility if infra naming changes
    ALLOWED_HOSTS: List[str] = Field(default_factory=list)
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default=["http://127.0.0.1:3000", "http://localhost:3000"]
    )

    # --- Authentication Logic ---
    COOKIE_SECURE: bool = Field(default=False)
    COOKIE_SAMESITE: str = Field(default="lax")
    
    ACCESS_TOKEN_EXPIRES_MINUTES: int = Field(default=300, gt=0)
    REFRESH_TOKEN_EXPIRES_DAYS: int = Field(default=7, gt=0)
    PASSWORD_RESET_CODE_EXPIRE_MINUTES: int = Field(default=15, gt=0)

    # --- Email Configuration ---
    MAIL_USERNAME: str = Field(default="test")
    MAIL_PASSWORD: str = Field(default="test")
    MAIL_FROM: str = Field(default="test@email.com")
    MAIL_PORT: int = Field(default=587)
    MAIL_SERVER: str = Field(default="test")
    MAIL_STARTTLS: bool = Field(default=False)
    MAIL_SSL_TLS: bool = Field(default=True)
    USE_CREDENTIALS: bool = Field(default=True)
    VALIDATE_CERTS: bool = Field(default=True)

    # --- LLM Settings (Required) ---
    GEMINI_MODEL: str = Field(default="gemini-1.5-pro")
    GOOGLE_API_KEY: str = Field(...)
    TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    MAX_OUTPUT_TOKENS: int = Field(default=2048, gt=0)

    # --- Quiz Settings ---
    QUIZ_NUM_QUESTIONS: int = Field(default=10, gt=0)

    # --- Constants ---
    API_V1_STR: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("COOKIE_SECURE", mode="after")
    @classmethod
    def validate_cookie_security(cls, v: bool, info) -> bool:
        """Ensure production always uses secure cookies."""
        if info.data.get("ENVIRONMENT") == "prod" and not v:
            raise ValueError("COOKIE_SECURE must be True in production")
        return v

settings = Settings()


@lru_cache
def load_google_llm():
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=settings.TEMPERATURE,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
        convert_system_message_to_human=True
    )