from datetime import datetime, timezone
import enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum, Integer, String, DateTime, ForeignKey, JSON, UUID, func

from .base import Base


class PlaylistLevel(str, enum.Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


class Playlist(Base):
    __tablename__ = 'playlists'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    level: Mapped[PlaylistLevel] = mapped_column(Enum(PlaylistLevel), default=PlaylistLevel.BEGINNER)
    timeline: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    objectives: Mapped[list[str]] = mapped_column(JSON)
    # content: Mapped[dict] = mapped_column(JSON, nullable=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    modules = relationship("Module", back_populates="playlist", cascade="all, delete-orphan")
