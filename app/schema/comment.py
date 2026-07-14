from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class CommentBase(BaseModel):
    content: str


class CommentCreate(CommentBase):
    post_id: int


class CommentUpdate(BaseModel):
    content: Optional[str] = None


class CommentResponse(CommentBase):
    id: int
    user_id: UUID
    post_id: int
    created_at: datetime
    user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
