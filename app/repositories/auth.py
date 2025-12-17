from sqlalchemy import func, select, update
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.security import Hasher
from ..models.user import PasswordResetToken, User


class PasswordResetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add(self, token: PasswordResetToken):
        self.session.add(token)
        await self.session.flush()

    async def verify_reset_code(
        self, code: str, email: str
    ) -> PasswordResetToken | None:
        """
        Return the valid PasswordResetToken DB object (not boolean).
        This is preferred so the caller can access token.user_id etc
        and so we can mark it used atomically in reset_password_with_token.
        """
        code_hash = Hasher.hash_code(code)
        stmt = (
            select(PasswordResetToken)
            .join(User)
            .options(joinedload(PasswordResetToken.user))
            .where(
                PasswordResetToken.code_hash == code_hash,
                PasswordResetToken.is_used.is_(False),
                PasswordResetToken.expires_at > func.now(),
                User.email == email,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def invalidate_unused_verification_codes(self, user: User):
        stmt = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.is_used.is_(False),
            )
            .values(is_used=True)
        )
        await self.session.execute(stmt)