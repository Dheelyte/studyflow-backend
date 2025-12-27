from uuid import UUID
from pydantic import UUID4, BaseModel, ConfigDict
from datetime import datetime

from ..models.progress import UserPlaylistStatus


class UserPlaylistCreate(BaseModel):
    playlist_id: int
    user_id: UUID4


class UserPlaylistUpdate(BaseModel):
    status: UserPlaylistStatus


class ListPlaylistResponse(BaseModel):
    id: int
    title: str


class UserPlaylistResponse(BaseModel):
    id: int
    user_id: UUID
    created_at: datetime
    playlist: ListPlaylistResponse

    model_config = ConfigDict(from_attributes=True)
