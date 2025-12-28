from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey
from .base import Base


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    order: Mapped[int] = mapped_column(Integer)

    lesson = relationship("Lesson", back_populates="resources")
