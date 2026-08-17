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
    # Set when the course was generated with a level customization.
    level: Optional[str] = None


class PlaylistResponse(BaseModel):
    id: int
    title: str
    description: str | None
    objectives: list[str] | None
    # Enum on the model; the str value ("Beginner") is what clients render.
    level: str | None = None
    user_id: UUID
    created_at: datetime
    is_public: bool = False
    slug: str | None = None

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
