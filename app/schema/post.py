from uuid import UUID
from pydantic import BaseModel, ConfigDict
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
    user_name: str | None = None
    community_id: int
    # Only populated for the general feed (feed/explore), where a post's
    # community isn't otherwise obvious. Null inside a single community's page.
    community_name: str | None = None
    comments_count: int
    likes_count: int = 0
    liked_by_user: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
