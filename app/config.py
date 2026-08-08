import asyncio
import weakref
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_google_genai import ChatGoogleGenerativeAI

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Branding ---
    APP_NAME: str = Field(default="Primerly")

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
    COOKIE_DOMAIN: str = Field(default="")
    
    ACCESS_TOKEN_EXPIRES_MINUTES: int = Field(default=300, gt=0)
    REFRESH_TOKEN_EXPIRES_DAYS: int = Field(default=7, gt=0)
    PASSWORD_RESET_CODE_EXPIRE_MINUTES: int = Field(default=15, gt=0)

    # --- Email Configuration ---
    MAIL_USERNAME: str = Field(default="test")
    MAIL_PASSWORD: str = Field(default="test")
    MAIL_FROM: str = Field(default="test@email.com")
    MAIL_PORT: int = Field(default=587)
    MAIL_SERVER: str = Field(default="dev")
    MAIL_STARTTLS: bool = Field(default=False)
    MAIL_SSL_TLS: bool = Field(default=True)
    USE_CREDENTIALS: bool = Field(default=True)
    VALIDATE_CERTS: bool = Field(default=True)
    TEMPLATE_FOLDER: str = Field(default="app/templates")

    # --- Screen Tutor ---
    # Deprecated: superseded by the plan-aware *_SCREEN_TUTOR_DAILY limits below.
    SCREEN_TUTOR_DAILY_LIMIT: int = Field(default=20, gt=0)

    # --- Billing / Plans ---
    BILLING_ENABLED: bool = Field(default=False)
    PAYSTACK_SECRET_KEY: str = Field(default="")
    PAYSTACK_PLAN_CODE_PRO_MONTHLY: str = Field(default="")
    PAYSTACK_PLAN_CODE_PRO_ANNUAL: str = Field(default="")
    PAYSTACK_PLAN_CODE_MAX_MONTHLY: str = Field(default="")
    PAYSTACK_PLAN_CODE_MAX_ANNUAL: str = Field(default="")

    # Tier limits (free / pro / max). Max's chat + screen tutor are displayed
    # "Unlimited" , the caps exist only as abuse brakes no human use reaches.
    FREE_COURSE_GENERATIONS_MONTHLY: int = Field(default=3, gt=0)
    PRO_COURSE_GENERATIONS_MONTHLY: int = Field(default=15, gt=0)
    MAX_COURSE_GENERATIONS_MONTHLY: int = Field(default=50, gt=0)

    FREE_CHAT_MESSAGES_DAILY: int = Field(default=10, gt=0)
    PRO_CHAT_MESSAGES_DAILY: int = Field(default=100, gt=0)
    MAX_CHAT_MESSAGES_DAILY: int = Field(default=1000, gt=0)

    FREE_SCREEN_TUTOR_DAILY: int = Field(default=10, gt=0)
    PRO_SCREEN_TUTOR_DAILY: int = Field(default=30, gt=0)
    MAX_SCREEN_TUTOR_DAILY: int = Field(default=500, gt=0)

    # --- LLM Settings (Required) ---
    GEMINI_MODEL: str = Field(default="")
    GOOGLE_API_KEY: str = Field(...)
    TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    MAX_OUTPUT_TOKENS: int = Field(default=2048, gt=0)
    USE_MOCK_DATA: bool = Field(...)

    # --- YouTube Data API ---
    YOUTUBE_API_KEY: str = Field(default="")

    # --- Google Auth Settings ---
    GOOGLE_OAUTH2_CLIENT_ID: str = Field(...)
    GOOGLE_OAUTH2_CLIENT_SECRET: str = Field(...)
    
    # --- Github Auth Settings ---
    SOCIAL_GITHUB_CLIENT_ID: str = Field(...)
    SOCIAL_GITHUB_CLIENT_SECRET: str = Field(...)
    
    # --- Apple Auth Settings ---
    APPLE_CLIENT_ID: str = Field(...)
    APPLE_TEAM_ID: str = Field(...)
    APPLE_KEY_ID: str = Field(...)
    APPLE_PRIVATE_KEY: str = Field(...)

    # --- Quiz Settings ---
    QUIZ_NUM_QUESTIONS: int = Field(default=10, gt=0)

    # --- Constants ---
    API_V1_STR: str = Field(default="/api/v1")
    FRONTEND_URL: str = Field(default="http://127.0.0.1:3000")
    FRONTEND_DASHBOARD_URL: str = Field(default="http://127.0.0.1:3000/dashboard")
    FRONTEND_REDIRECT_URL: str = Field(default="http://127.0.0.1:3000/login")
    BACKEND_URL: str = Field(default="http://127.0.0.1:8000/api/v1")

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


def _build_google_llm():
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=settings.TEMPERATURE,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
        convert_system_message_to_human=True
    )


# The client holds an httpx.AsyncClient bound to the event loop it was built on,
# so it cannot be a process-wide singleton: under Lambda, Mangum runs each
# invocation in its own asyncio.run() and closes the loop afterwards, which left
# a warm container reusing a dead client ("Event loop is closed") on every
# request after the first. Keying the cache on the running loop keeps one client
# per invocation there, while a long-lived server (uvicorn) has a single loop and
# so still reuses one client for the life of the process. Weak keys let the entry
# go when the loop is collected.
_llm_by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, ChatGoogleGenerativeAI]" = (
    weakref.WeakKeyDictionary()
)


def load_google_llm():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from sync code: no loop to bind to, so don't cache it.
        return _build_google_llm()

    llm = _llm_by_loop.get(loop)
    if llm is None:
        llm = _build_google_llm()
        _llm_by_loop[loop] = llm
    return llm