from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}

    for error in exc.errors():
        # Get the field name (last element of the loc tuple)
        # e.g., ('body', 'username') -> 'username'
        field_name = str(error["loc"][-1])
        message = error["msg"]

        errors[field_name] = message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=errors,
    )
