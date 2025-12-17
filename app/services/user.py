from typing import Annotated

from fastapi import Depends
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..exceptions.base import BadRequestError
from ..models.user import User
from ..repositories.user import UserRepository
from ..schema.user import PasswordChangeData, UserCreate
from ..utils.security import Hasher

password_hash = PasswordHash.recommended()


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
        
    async def register_user(self, user_data: UserCreate) -> User:
        existing_user = await self.repo.get_by_email(user_data.email)
        if existing_user:
            raise BadRequestError("A user with this email exists")
        
        user = User(
            email=user_data.email.lower(),
            password_hash=Hasher.get_password_hash(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            is_active=True,
            is_verified=False,
        )
        await self.repo.add(user)
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.repo.get_by_email(email)

    async def update_password(self, user: User, old_password: str, new_password: str) -> None:
        """Update user password."""
        if not Hasher.verify_password(
            old_password, user.password_hash
        ):
            raise BadRequestError("Incorrect old password")
        user.password_hash = Hasher.get_password_hash(new_password)


def get_user_repo(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(session)

def get_user_service(
    repo: UserRepository = Depends(get_user_repo)
) -> UserService:
    return UserService(repo)

UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
