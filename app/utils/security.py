import hashlib
import re
import secrets

from fastapi import Request
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


class Hasher:
    @staticmethod
    def get_password_hash(password: str) -> str:
        return password_hash.hash(password)

    @staticmethod
    def verify_password(password: str, hash: str) -> bool:
        return password_hash.verify(password, hash)

    @staticmethod
    def hash_code(code: str) -> str:
        """Hash the reset code for storage."""
        return hashlib.sha256(code.encode()).hexdigest()


class TokenGenerator:
    @staticmethod
    def generate_code() -> str:
        """Returns (plain_code, hashed_code)."""
        code = secrets.randbelow(1000000)
        return f"{code:06d}"  # Pad with zeros: 000123


class OAuthStateService:
    @staticmethod
    def get_oauth_state_robust(request: Request) -> str | None:
        # 1. Try standard retrieval
        state = request.cookies.get("oauth_state")
        if state:
            return state

        # 2. Fallback: Search all cookie values for the merged token
        for key, value in request.cookies.items():
            if "oauth_state=" in value:
                match = re.search(r'oauth_state=([a-zA-Z0-9\-\_]+)', value)
                if match:
                    return match.group(1)

        # 3. Last Resort: Parse the raw Cookie header
        raw_cookie = request.headers.get("cookie", "")
        if "oauth_state=" in raw_cookie:
            match = re.search(r'oauth_state=([a-zA-Z0-9\-\_]+)', raw_cookie)
            if match:
                return match.group(1)

        return None