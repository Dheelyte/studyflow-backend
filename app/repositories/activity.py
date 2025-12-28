from datetime import date, timedelta
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import UserDailyActivity

class ActivityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_daily_activity(self, user_id: UUID, activity_date: date) -> UserDailyActivity | None:
        stmt = select(UserDailyActivity).where(
            UserDailyActivity.user_id == user_id,
            UserDailyActivity.date == activity_date
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_activities(self, user_id: UUID, days: int = None) -> list[UserDailyActivity]:
        if days:
            stmt = select(UserDailyActivity).where(
                UserDailyActivity.user_id == user_id,
                UserDailyActivity.date >= date.today() - timedelta(days=days)
            ).order_by(UserDailyActivity.date.asc())
        else:
            stmt = select(UserDailyActivity).where(
                UserDailyActivity.user_id == user_id
            ).order_by(UserDailyActivity.date.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add(self, activity: UserDailyActivity):
        self.session.add(activity)
        await self.session.flush()
        return activity
