import enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Enum, ForeignKey, Boolean, DateTime, UniqueConstraint
from datetime import datetime, timezone

from ..models.base import Base


class UserPlaylistStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class UserPlaylist(Base):
    __tablename__ = 'user_playlists'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    playlist_id: Mapped[int] = mapped_column(ForeignKey('playlists.id'))
    status: Mapped[UserPlaylistStatus] = mapped_column(Enum(UserPlaylistStatus), default=UserPlaylistStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    playlist = relationship("Playlist")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'playlist_id', name='unique_user_playlist'),
    )


class UserResourceProgress(Base):
    __tablename__ = 'user_resource_progress'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    resource_id: Mapped[int] = mapped_column(ForeignKey('resources.id'))
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'resource_id', name='unique_user_resource_progress'),
    )


class UserModuleProgress(Base):
    __tablename__ = 'user_module_progress'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    module_id: Mapped[int] = mapped_column(ForeignKey('modules.id'))
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'module_id', name='unique_user_module_progress'),
    )
