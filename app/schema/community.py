from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CommunityBase(BaseModel):
    name: str
    description: Optional[str] = None


class CommunityCreate(CommunityBase):
    pass


class CommunityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CommunityResponse(CommunityBase):
    id: int
    created_at: datetime
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class CommunityDetailResponse(CommunityResponse):
    member_count: int = 0
    is_member: bool
