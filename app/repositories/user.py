from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_expired_paid_users(self, cutoff, limit: int) -> list[User]:
        """Paid users whose period ended before `cutoff` (period end + grace).

        Feeds the scheduled sweep. Oldest first so a backlog drains in order
        rather than the same rows being retried every run.
        """
        stmt = (
            select(User)
            .where(
                User.plan != "free",
                User.plan_expires_at.isnot(None),
                User.plan_expires_at < cutoff,
            )
            .order_by(User.plan_expires_at)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    
    async def add(self, user: User):
        self.session.add(user)
        await self.session.flush()
        return user