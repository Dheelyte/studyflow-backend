import hashlib
import secrets

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
