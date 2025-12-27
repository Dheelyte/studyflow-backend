from .base import Base
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import Integer, String, ForeignKey


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    estimated_time: Mapped[str] = mapped_column(String)
    order: Mapped[int] = mapped_column(Integer)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"))
