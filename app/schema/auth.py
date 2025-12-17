import re
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginData(BaseModel):
    email: EmailStr
    password: str


class PasswordResetVerify(BaseModel):
    is_valid: bool


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetData(BaseModel):
    """Verify reset code and set new password."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is 6 digits."""
        if not re.match(r"^\d{6}$", v):
            raise ValueError("Code must be exactly 6 digits")
        return v

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


class PasswordResetCodeCheck(BaseModel):
    """Check if reset code is valid (without resetting password)."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is 6 digits."""
        if not re.match(r"^\d{6}$", v):
            raise ValueError("Code must be exactly 6 digits")
        return v
