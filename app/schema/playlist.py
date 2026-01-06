from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..models.playlist import PlaylistLevel


class PlaylistCreate(BaseModel):
    title: str
    level: PlaylistLevel
    timeline: str
    description: str
    objectives: list[str]
    content: Optional[Dict[str, Any]] = None


class PlaylistResponse(BaseModel):
    id: int
    title: str
    level: PlaylistLevel
    timeline: str
    description: str | None
    objectives: list[str] | None
    user_id: UUID
    created_at: datetime
    #content: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ResourceRead(BaseModel):
    id: int
    title: str
    url: str
    type: str
    description: str
    order: int
    is_completed: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class LessonRead(BaseModel):
    id: int
    title: str
    estimated_time: str
    order: int
    resources: List[ResourceRead] = []
    
    model_config = ConfigDict(from_attributes=True)


class ModuleRead(BaseModel):
    id: int
    title: str
    description: str
    topics_covered: list[str]
    order: int
    quiz_completed: bool = False
    lessons: List[LessonRead] = []
    
    model_config = ConfigDict(from_attributes=True)


class PlaylistDetailSchema(PlaylistResponse):
    modules: List[ModuleRead] = []

