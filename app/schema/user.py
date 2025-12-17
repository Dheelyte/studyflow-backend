from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str):
        if len(v) < 8:
            raise ValueError("Password can not be less than 8 characters")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one capital letter")
        return v


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class PasswordChangeData(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_passwords_match(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # This runs before instantiation, checking the raw dictionary input
        if isinstance(values, dict):
            old_pw = values.get("old_password")
            new_pw = values.get("new_password")

            if old_pw and new_pw and old_pw == new_pw:
                # Raise the error with a specific location for better feedback
                raise ValueError("New password must be different from the old one")

        return values
