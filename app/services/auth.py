from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..repositories.user import UserRepository
from ..exceptions.base import BadRequestError, UnauthorizedError
from ..repositories.auth import PasswordResetRepository
from ..config import settings
from ..models.user import PasswordResetToken, User
from ..services.email import EmailService
from ..services.user import UserService, get_user_repo
from ..utils.security import Hasher, TokenGenerator


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def authenticate_user(self, email: str, password: str) -> User | None:
        user = await self.user_repo.get_by_email(email)

        if not user or not Hasher.verify_password(password, user.password_hash):
            raise BadRequestError("Incorrect email or password")
        
        if not user.is_active:
            raise UnauthorizedError("User is inactive")
        
        return user


class AuthTokenService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    async def refresh_user_token(self, request: Request, response: Response):
        token = request.cookies.get("refresh_token")
        if not token:
            raise UnauthorizedError("Refresh token not found")
        
        email = self.verify_refresh_token(token)
        if not email:
            raise UnauthorizedError("Refresh token is expired or invalid")

        user = await self.user_repo.get_by_email(email)
        if not user:
            raise BadRequestError("User not found")
        if not user.is_active:
            raise UnauthorizedError("User is inactive")
        
        new_access_token = self.create_access_token(data={"sub": user.email})
        self.set_auth_cookies(response, new_access_token)

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES
        )
        to_encode.update({"exp": expire, "token_type": "access"})

        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token with longer expiration."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRES_DAYS
        )

        to_encode.update({"exp": expire, "token_type": "refresh"})
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    def verify_refresh_token(self, refresh_token: str) -> str | None:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            email: str = payload.get("sub")
            token_type: str = payload.get("token_type")

            if not email or token_type != "refresh":
                return None
            return email
        except jwt.PyJWTError:
            return None

    def set_auth_cookies(
        self, response: Response, access_token: str, refresh_token: str = None
    ):
        """Set HTTP-only cookies for access and refresh tokens."""
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60,
            path="/",
        )
        if refresh_token:
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=settings.COOKIE_SECURE,
                samesite=settings.COOKIE_SAMESITE,
                max_age=settings.REFRESH_TOKEN_EXPIRES_DAYS * 24 * 60 * 60,
                path="/api/v1/auth/refresh",
            )

    def clear_auth_cookies(self, response: Response):
        """Clear authentication cookies."""
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="refresh_token", path="/api/v1/auth/refresh")


class PasswordResetService:
    def __init__(self, reset_repo: PasswordResetRepository, user_repo: UserRepository):
        self.user_repo = user_repo
        self.reset_repo = reset_repo

    async def request_password_reset(self, email: str):
        user = await self.user_repo.get_by_email(email)
        if user:
            code = await self._create_reset_code(user)
            await self._send_password_reset_email(user, code)

    async def reset_password_with_token(self, reset_data):
        """
        Update the user's password and mark the token used.
        """
        valid_token = await self.verify_reset_code(reset_data.code, reset_data.email)
        if Hasher.verify_password(
            reset_data.new_password, valid_token.user.password_hash
        ):
            raise BadRequestError("New password must not be the same with the old one")
        user: User = valid_token.user
        user.password_hash = Hasher.get_password_hash(reset_data.new_password)
        valid_token.is_used = True

    async def _create_reset_code(self, user: User) -> str:
        """
        Create a password reset code for user.
        Invalidates all previous codes.

        Returns: The unhashed code to send to user
        """
        # Invalidate all previous unused codes for this user
        await self._invalidate_unused_verification_codes(user)

        code = TokenGenerator.generate_code()
        code_hash = Hasher.hash_code(code)

        token = PasswordResetToken(
            code_hash=code_hash,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES),
            is_used=False,
        )
        await self.reset_repo.add(token)

        return code

    async def verify_reset_code(
        self, code: str, email: str
    ) -> PasswordResetToken | None:
        valid_token = await self.reset_repo.verify_reset_code(code, email)
        if not valid_token:
            raise BadRequestError("Invalid or expired code")
        return valid_token

    async def _invalidate_unused_verification_codes(self, user: User):
        """Invalidate other unused tokens"""
        await self.reset_repo.invalidate_unused_verification_codes(user)

    async def _send_password_reset_email(self, user: User, code: str):
        await EmailService.send_email(
            recipients=[user.email],
            subject="Reset your password",
            body=f"Password reset code: {code} for {user.email}",
        )


def get_reset_repo(session: AsyncSession = Depends(get_session)) -> PasswordResetRepository:
    return PasswordResetRepository(session)

def get_password_reset_service(
    reset_repo: PasswordResetRepository = Depends(get_reset_repo),
    user_repo: UserRepository = Depends(get_user_repo)

) -> PasswordResetService:
    return PasswordResetService(reset_repo, user_repo)

def get_token_service(
    user_repo: AuthTokenService = Depends(get_user_repo)
) -> AuthTokenService:
    return AuthTokenService(user_repo)

def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repo)
) -> AuthService:
    return AuthService(user_repo)

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AuthTokenServiceDep = Annotated[AuthTokenService, Depends(get_token_service)]
PasswordResetServiceDep = Annotated[PasswordResetService, Depends(get_password_reset_service)]
