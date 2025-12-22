from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PostBase(BaseModel):
    content: str


class PostCreate(PostBase):
    community_id: int


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class PostResponse(PostBase):
    id: int
    user_id: UUID
    community_id: int
    comments_count: int
    created_at: datetime

    class Config:
        from_attributes = True
