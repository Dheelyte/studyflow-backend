from typing import Annotated

from fastapi import Depends, Request

from ..exceptions.base import UnauthorizedError
from ..services.auth import AuthTokenServiceDep
from ..models.user import User
from ..utils.security import CookieService



async def get_auth_user(
    request: Request, token_service: AuthTokenServiceDep
):   
    token = CookieService.get_cookie(request, "access_token")
    if not token:
        raise UnauthorizedError("Not authenticated")
    
    email = token_service.verify_access_token(token)
    print("DEBUG: Token", token)
    print("DEBUG: Email", email)
    if not email:
        raise UnauthorizedError("Invalid or expired token")
        
    user = await token_service.get_user_from_token(token)

    if not user.is_active:
        raise UnauthorizedError("User is inactive")

    return user


async def optional_get_auth_user(
    request: Request, token_service: AuthTokenServiceDep
) -> User | None:
    token = CookieService.get_cookie(request, "access_token")
    if not token:
        return None
    
    email = token_service.verify_access_token(token)
    if not email:
        return None
        
    try:
        user = await token_service.get_user_from_token(token)
        if not user.is_active:
            raise UnauthorizedError("User is inactive")
        return user
    except:
        return None


AuthUserDep = Annotated[User, Depends(get_auth_user)]
OptionalAuthUserDep = Annotated[User | None, Depends(optional_get_auth_user)]
