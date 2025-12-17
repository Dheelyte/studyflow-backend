from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from .config import settings
from .middlewares.security import AllowedHostMiddlware
from .middlewares.utils import TimingMiddleware
from .routers import auth, users
from .schema.base import CustomValidationErrorSchema
from .exceptions.base import register_app_exceptions


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="StudyFlow API Documentation",
    responses={
        422: {
            "description": "Validation Error",
            "model": CustomValidationErrorSchema,
        }
    },
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AllowedHostMiddlware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)

API_V1_STR = settings.API_V1_STR
app.include_router(auth.router, prefix=API_V1_STR)
app.include_router(users.router, prefix=API_V1_STR)

register_app_exceptions(app)


@app.get("/")
async def health_status():
    return {"status": "healthy"}


handler = Mangum(app)
