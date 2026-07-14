from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any, List

from .topic import TopicRead


class PlaylistCreate(BaseModel):
    title: str
    description: str
    objectives: list[str]
    content: Optional[Dict[str, Any]] = None


class PlaylistResponse(BaseModel):
    id: int
    title: str
    description: str | None
    objectives: list[str] | None
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonRead(BaseModel):
    id: int
    title: str
    estimated_time: str
    order: int
    topics: List[TopicRead] = []

    model_config = ConfigDict(from_attributes=True)


class ModuleRead(BaseModel):
    id: int
    title: str
    description: str
    order: int
    quiz_completed: bool = False
    lessons: List[LessonRead] = []

    model_config = ConfigDict(from_attributes=True)


class PlaylistDetailSchema(PlaylistResponse):
    modules: List[ModuleRead] = []
