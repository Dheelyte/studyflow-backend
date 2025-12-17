
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .security import RequestValidationError, validation_exception_handler


class BadRequestError(Exception):
    """Base class for all 400 errors"""
    pass

class UnauthorizedError(Exception):
    pass


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


def register_app_exceptions(app: FastAPI):
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(BadRequestError, bad_request_handler)
    app.add_exception_handler(UnauthorizedError, unauthorized_request_handler)
