from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, ForeignKey, JSON
from .base import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), unique=True)
    questions: Mapped[list[dict]] = mapped_column(JSON)

    module = relationship("Module", back_populates="quiz")
