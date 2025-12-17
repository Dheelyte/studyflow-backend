from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings


class AllowedHostMiddlware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if settings.DEBUG or host in settings.ALLOWED_HOSTS:
            return await call_next(request)
        raise HTTPException(status_code=400, detail="Invalid host")
