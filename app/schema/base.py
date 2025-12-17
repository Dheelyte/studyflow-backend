from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class MsgResponse(BaseModel):
    message: str


class DataResponse(BaseModel, Generic[T]):
    data: T


class MsgDataResponse(BaseModel, Generic[T]):
    message: str
    data: T


class CustomValidationErrorSchema(BaseModel):
    detail: str
    errors: dict[str, str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "Validation Failed",
                "errors": {
                    "form_field1": "error message",
                    "form_field2": "error message",
                },
            }
        }
    }
