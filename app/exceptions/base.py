
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .security import RequestValidationError, validation_exception_handler


class BadRequestError(Exception):
    """Base class for all 400 errors"""
    pass

class UnauthorizedError(Exception):
    pass

class NotFoundError(Exception):
    pass

class ForbiddenError(Exception):
    """Authenticated, but not allowed to act on this resource."""
    pass

class QuotaExceededError(Exception):
    """A plan limit was hit. Carries a machine-readable body the frontend
    uses to show the upgrade prompt (HTTP 402)."""

    def __init__(self, metric: str, limit: int, used: int, plan: str, detail: str | None = None):
        self.metric = metric
        self.limit = limit
        self.used = used
        self.plan = plan
        self.detail = detail or f"You've reached your {metric.replace('_', ' ')} limit for this period."
        super().__init__(self.detail)


async def bad_request_handler(request: Request, exc: BadRequestError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )

async def unauthorized_request_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
    )

async def notfound_request_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )

async def forbidden_request_handler(request: Request, exc: ForbiddenError):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )

async def quota_exceeded_handler(request: Request, exc: QuotaExceededError):
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={
            "detail": exc.detail,
            "code": "quota_exceeded",
            "metric": exc.metric,
            "limit": exc.limit,
            "used": exc.used,
            "plan": exc.plan,
        },
    )


def register_app_exceptions(app: FastAPI):
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(BadRequestError, bad_request_handler)
    app.add_exception_handler(UnauthorizedError, unauthorized_request_handler)
    app.add_exception_handler(NotFoundError, notfound_request_handler)
    app.add_exception_handler(ForbiddenError, forbidden_request_handler)
    app.add_exception_handler(QuotaExceededError, quota_exceeded_handler)
