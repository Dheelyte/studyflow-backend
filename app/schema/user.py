from datetime import datetime
from math import floor, sqrt
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, computed_field


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


from enum import Enum

class LevelTitle(str, Enum):
    NOVICE = "Explorer"
    LEARNER = "Dedicated Learner"
    SEEKER = "Knowledge Seeker"
    SCHOLAR = "Scholar"
    MASTER = "Master"
    GRANDMASTER = "Grandmaster"

class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    current_streak: int
    longest_streak: int
    last_active_date: datetime | None
    total_xp: int = 0
    plan: str = "free"

    @computed_field
    @property
    def level(self) -> int:
        return floor(0.1 * sqrt(self.total_xp))

    @computed_field
    @property
    def level_name(self) -> LevelTitle:
        lvl = self.level
        if lvl < 5:
            return LevelTitle.NOVICE
        elif lvl < 10:
            return LevelTitle.LEARNER
        elif lvl < 20:
            return LevelTitle.SEEKER
        elif lvl < 30:
            return LevelTitle.SCHOLAR
        elif lvl < 50:
            return LevelTitle.MASTER
        else:
            return LevelTitle.GRANDMASTER


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
