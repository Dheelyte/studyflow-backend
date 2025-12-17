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
    
    async def add(self, user: User):
        self.session.add(user)
        await self.session.flush()
        return user