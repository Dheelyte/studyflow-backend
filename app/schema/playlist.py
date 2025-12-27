from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any

from ..models.playlist import PlaylistLevel


class PlaylistCreate(BaseModel):
    title: str
    level: PlaylistLevel
    timeline: str
    content: Optional[Dict[str, Any]] = None


class PlaylistResponse(BaseModel):
    id: int
    title: str
    level: PlaylistLevel
    timeline: str
    user_id: UUID
    created_at: datetime
    content: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
