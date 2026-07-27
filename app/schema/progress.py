from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from ..models.progress import UserPlaylistStatus


class UserPlaylistCreate(BaseModel):
    playlist_id: int
    user_id: UUID


class UserPlaylistUpdate(BaseModel):
    status: UserPlaylistStatus


class ListPlaylistResponse(BaseModel):
    id: int
    title: str
    slug: str | None = None
    level: str | None = None


class PlaylistProgress(BaseModel):
    completed_modules: int
    total_modules: int
    percentage: float


class UserPlaylistResponse(BaseModel):
    id: int
    user_id: UUID
    created_at: datetime
    playlist: ListPlaylistResponse
    progress: PlaylistProgress | None = None

    model_config = ConfigDict(from_attributes=True)


class UserTopicProgressResponse(BaseModel):
    topic_id: int
    is_completed: bool
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
