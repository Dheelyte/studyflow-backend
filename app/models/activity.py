
from sqlalchemy import Integer, Date, ForeignKey, UniqueConstraint, UUID
from sqlalchemy.orm import mapped_column, Mapped
from datetime import date

from .base import Base

class UserDailyActivity(Base):
    __tablename__ = "user_daily_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    activity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="unique_user_daily_activity"),
    )
