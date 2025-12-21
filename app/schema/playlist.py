from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from ..schema.resource import ResourceBase


class CurriculumRequest(BaseModel):
    topic: str
    experience_level: str
    learn_duration: str

class CurriculumResponse(BaseModel):
    title: str
    summary: str
    resources: ResourceBase


class PlaylistStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class PlaylistBase(BaseModel):
    topic: str
    status: PlaylistStatus = PlaylistStatus.PENDING

class PlaylistCreate(BaseModel):
    user_id: int

class PlaylistUpdate(BaseModel):
    status: PlaylistStatus

class PlaylistResponse(PlaylistBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
