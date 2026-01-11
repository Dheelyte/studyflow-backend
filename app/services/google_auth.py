import httpx
import jwt

from attrs import define, field
from fastapi import HTTPException, Depends
from urllib.parse import urlencode
from random import SystemRandom
from string import ascii_letters, digits
from typing import Annotated

from ..config import settings
from ..models.user import User
from ..services.user import get_user_repo
from ..repositories.user import UserRepository


@define
class GoogleAccessTokens:
    id_token: str
    access_token: str
    
    def decode_id_token(self) -> dict:
        # options={"verify_signature": False} is safe here because 
        # we received this directly from Google via TLS
        return jwt.decode(self.id_token, options={"verify_signature": False})


class GoogleUserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_or_create_google_user(self, email: str, user_info: dict) -> User:
        """
        Async implementation of get_or_create.
        """
        existing_user = await self.user_repo.get_by_email(email)

        if existing_user:
            return existing_user

        # Create new user
        new_user = User(
            email=email,
            first_name=user_info.get("given_name", ""),
            last_name=user_info.get("family_name", ""),
            password_hash="",
            is_active=True,
            # Handle password logic here (e.g., set hash to un-guessable string)
        )
        await self.user_repo.add(new_user)
        return new_user


class GoogleRawLoginFlowService:
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    
    SCOPES = [
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid",
    ]

    def __init__(self):
        self.client_id = settings.GOOGLE_OAUTH2_CLIENT_ID
        self.client_secret = settings.GOOGLE_OAUTH2_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/auth/callback/google" 

    @staticmethod
    def _generate_state_token(length=30):
        rand = SystemRandom()
        chars = ascii_letters + digits
        return "".join(rand.choice(chars) for _ in range(length))

    def get_authorization_url(self) -> tuple[str, str]:
        state = self._generate_state_token()
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.SCOPES),
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "select_account",
        }
        url = f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"
        return url, state

    async def get_tokens(self, code: str) -> GoogleAccessTokens:
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        
        # Use httpx for Async HTTP requests (Scalability Requirement)
        async with httpx.AsyncClient() as client:
            response = await client.post(self.GOOGLE_TOKEN_URL, data=data)
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to retrieve tokens from Google")
            
            tokens = response.json()
            return GoogleAccessTokens(
                id_token=tokens["id_token"], 
                access_token=tokens["access_token"]
            )

    async def get_user_info(self, google_tokens: GoogleAccessTokens) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GOOGLE_USER_INFO_URL, 
                params={"access_token": google_tokens.access_token}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            return response.json()


def get_google_user_service(
    repo: UserRepository = Depends(get_user_repo)
) -> GoogleUserService:
    return GoogleUserService(repo)

def get_google_service() -> GoogleRawLoginFlowService:
    return GoogleRawLoginFlowService()

GoogleUserServiceDep = Annotated[GoogleUserService, Depends(get_google_user_service)]
GoogleRawLoginFlowServiceDep = Annotated[GoogleRawLoginFlowService, Depends(get_google_service)]
