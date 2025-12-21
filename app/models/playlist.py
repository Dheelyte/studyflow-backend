from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum
from datetime import datetime, timezone
import enum
from .base import Base


class PlaylistStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Playlist(Base):
    __tablename__ = "playlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    topic: Mapped[str] = mapped_column(String)
    status: Mapped[PlaylistStatus] = mapped_column(Enum(PlaylistStatus), default=PlaylistStatus.PENDING)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
