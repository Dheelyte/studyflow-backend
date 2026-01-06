from uuid import UUID
from pydantic import UUID4, BaseModel, ConfigDict
from datetime import datetime

from ..models.playlist import PlaylistLevel
from ..models.progress import UserPlaylistStatus


class UserPlaylistCreate(BaseModel):
    playlist_id: int
    user_id: UUID4


class UserPlaylistUpdate(BaseModel):
    status: UserPlaylistStatus


class ListPlaylistResponse(BaseModel):
    id: int
    title: str
    level: PlaylistLevel


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


class UserResourceProgressResponse(BaseModel):
    resource_id: int
    is_completed: bool
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
