from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ScreenTutorUsage(Base):
    """One row per user per day, for the screen tutor's daily question quota.

    Only a count is kept , captured frames are never written anywhere.
    """

    __tablename__ = 'screen_tutor_usage'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
    usage_date: Mapped[date] = mapped_column(Date, index=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'usage_date', name='unique_user_screen_tutor_day'),
    )
