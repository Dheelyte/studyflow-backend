import httpx
from uuid import uuid4
from attrs import define
from fastapi import HTTPException, Depends
from urllib.parse import urlencode
from random import SystemRandom
from string import ascii_letters, digits
from typing import Annotated, Optional

from ..config import settings
from ..models.user import User
from ..services.user import get_user_repo
from ..repositories.user import UserRepository


@define
class GithubAccessTokens:
    access_token: str
    token_type: str
    scope: str


class GithubUserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_or_create_github_user(self, email: str, user_info: dict) -> User:
        """
        Async implementation of get_or_create for Github users.
        """
        existing_user = await self.user_repo.get_by_email(email)

        if existing_user:
            return existing_user

        # Create new user
        # Github names might be split or just 'name'
        full_name = user_info.get("name") or user_info.get("login", "")
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        new_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password_hash=uuid4().hex,
            is_active=True,
        )
        await self.user_repo.add(new_user)
        return new_user


class GithubRawLoginFlowService:
    GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
    GITHUB_USER_INFO_URL = "https://api.github.com/user"
    GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"
    
    def __init__(self):
        self.client_id = settings.SOCIAL_GITHUB_CLIENT_ID
        self.client_secret = settings.SOCIAL_GITHUB_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/auth/callback/github" 

    @staticmethod
    def _generate_state_token(length=30):
        rand = SystemRandom()
        chars = ascii_letters + digits
        return "".join(rand.choice(chars) for _ in range(length))

    def get_authorization_url(self) -> tuple[str, str]:
        state = self._generate_state_token()
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        url = f"{self.GITHUB_AUTH_URL}?{urlencode(params)}"
        return url, state

    async def get_tokens(self, code: str) -> GithubAccessTokens:
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }
        headers = {"Accept": "application/json"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GITHUB_TOKEN_URL, 
                data=data, 
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to retrieve tokens from Github")
            
            payload = response.json()
            if "error" in payload:
                raise HTTPException(status_code=400, detail=f"Github Error: {payload.get('error_description')}")

            return GithubAccessTokens(
                access_token=payload["access_token"],
                token_type=payload.get("token_type", "bearer"),
                scope=payload.get("scope", "")
            )

    async def get_user_info(self, tokens: GithubAccessTokens) -> dict:
        headers = {"Authorization": f"Bearer {tokens.access_token}"}
        
        async with httpx.AsyncClient() as client:
            # 1. Get User Profile
            response = await client.get(self.GITHUB_USER_INFO_URL, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info from Github")
            
            user_info = response.json()
            
            # 2. If email is missing, fetch private emails
            if not user_info.get("email"):
                emails_response = await client.get(self.GITHUB_USER_EMAILS_URL, headers=headers)
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    # Find primary verified email
                    primary_email = next((e["email"] for e in emails if e["primary"] and e["verified"]), None)
                    # If no primary verified, verify any verified
                    if not primary_email:
                         primary_email = next((e["email"] for e in emails if e["verified"]), None)
                    
                    if primary_email:
                        user_info["email"] = primary_email
            
            if not user_info.get("email"):
                 raise HTTPException(status_code=400, detail="Could not retrieve verified email from Github account")

            return user_info


def get_github_user_service(
    repo: UserRepository = Depends(get_user_repo)
) -> GithubUserService:
    return GithubUserService(repo)

def get_github_service() -> GithubRawLoginFlowService:
    return GithubRawLoginFlowService()

GithubUserServiceDep = Annotated[GithubUserService, Depends(get_github_user_service)]
GithubRawLoginFlowServiceDep = Annotated[GithubRawLoginFlowService, Depends(get_github_service)]
