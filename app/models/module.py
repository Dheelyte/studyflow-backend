from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey
from .base import Base


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id"))
    order: Mapped[int] = mapped_column(Integer)

    playlist = relationship("Playlist", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", cascade="all, delete-orphan")
