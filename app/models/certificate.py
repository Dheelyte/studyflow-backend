from datetime import datetime
import uuid as uuid_module

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    UUID,
    func,
)

from .base import Base


def _new_verification_code() -> str:
    return uuid_module.uuid4().hex


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id"), nullable=False, index=True
    )
    verification_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        default=_new_verification_code,
    )
    playlist_title: Mapped[str] = mapped_column(String, nullable=False)
    recipient_name: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    playlist = relationship("Playlist", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "playlist_id", name="unique_user_playlist_certificate"
        ),
    )
