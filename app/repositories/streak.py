from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models.user import User


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
