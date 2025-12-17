import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        if process_time * 1000 < 100:
            process_time = process_time * 1000
            process_time_with_units = f"{process_time:.2f}ms"
        else:
            process_time_with_units = f"{process_time:.2f}s"
        response.headers["X-Process-Time"] = process_time_with_units
        return response
