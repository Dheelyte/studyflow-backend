from fastapi import Depends
from uuid import UUID
from datetime import datetime, timezone, date

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from ..repositories.activity import ActivityRepository
from ..models.activity import UserDailyActivity
from ..db.session import get_session


class ActivityService:
    def __init__(self, activity_repo: ActivityRepository):
        self.activity_repo = activity_repo
    
    async def get_user_activities(self, user_id: UUID, days: int = None):
        activities = await self.activity_repo.get_user_activities(user_id, days)
        return activities
    
    async def create_daily_activity(self, user_id: UUID, date: date):
        activity = UserDailyActivity(
            user_id=user_id,
            date=date,
            activity_count=1
        )
        await self.activity_repo.add(activity)
    
    async def update_daily_activity(self, user_id: UUID):
        today = datetime.now(timezone.utc).date()
        activity = await self.activity_repo.get_daily_activity(user_id, today)
        if activity:
            activity.activity_count += 1
        else:
            await self.create_daily_activity(user_id, today)


def get_activity_repo(session: AsyncSession = Depends(get_session)):
    return ActivityRepository(session)

def get_activity_service(activity_repo: ActivityRepository = Depends(get_activity_repo)):
    return ActivityService(activity_repo)

ActivityServiceDep = Annotated[ActivityService, Depends(get_activity_service)]
