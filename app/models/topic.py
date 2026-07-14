from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey
from .base import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    order: Mapped[int] = mapped_column(Integer)
    youtube_video_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))

    lesson = relationship("Lesson", back_populates="topics")
