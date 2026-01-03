from uuid import UUID
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models.user import User
from app.db.session import get_session


class StreakRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def update_user_streak(self, user_id: UUID):
        # Streak Logic
        user = await self.session.get(User, user_id)
        if user:
            now = datetime.now(timezone.utc)
            today_date = now.date()
            
            last_active = user.last_active_date
            if last_active:
                last_active_date = last_active.date()
                delta_days = (today_date - last_active_date).days
                
                if delta_days == 1:
                    # Consecutive day
                    user.current_streak += 1
                elif delta_days > 1:
                    # Broken streak
                    user.current_streak = 1
                # If delta_days == 0 (same day), do nothing
            else:
                # First activity
                user.current_streak = 1
            
            # Update longest streak
            if user.current_streak > user.longest_streak:
                user.longest_streak = user.current_streak
                
            user.last_active_date = now

    async def refresh_streak(self, user_id: UUID) -> User | None:
        """
        Checks if the user's streak is stale and resets it if necessary.
        Does not count as 'activity' for the day (does not increment).
        """
        user = await self.session.get(User, user_id)
        if not user:
            return None
            
        if not user.last_active_date:
            if user.current_streak > 0:
                user.current_streak = 0
                await self.session.flush()
            return user
            
        now = datetime.now(timezone.utc)
        today_date = now.date()
        last_active_date = user.last_active_date.date()
        delta_days = (today_date - last_active_date).days
        
        # If last active was yesterday (delta=1) or today (delta=0), streak is kept.
        # If delta > 1, streak is broken.
        if delta_days > 1:
            if user.current_streak > 0:
                user.current_streak = 0
                await self.session.flush()
                
        return user


def get_streak_repo(session: AsyncSession = Depends(get_session)) -> StreakRepository:
    return StreakRepository(session)

StreakRepoDep = Annotated[StreakRepository, Depends(get_streak_repo)]

