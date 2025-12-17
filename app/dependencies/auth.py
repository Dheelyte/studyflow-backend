from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWTError

from ..config import settings
from ..models.user import User
from ..services.user import UserRepoDep, UserServiceDep


async def get_current_user_from_cookie(request: Request, user_repo: UserRepoDep):
    access_token = request.cookies.get("access_token")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    if not access_token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        token_type: str = payload.get("token_type")

        if email is None or token_type != "access":
            raise credentials_exception

    except PyJWTError:
        raise credentials_exception

    user = await user_repo.get_by_email(email)

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user_from_cookie)],
):
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user


AuthUserDep = Annotated[User, Depends(get_current_active_user)]
