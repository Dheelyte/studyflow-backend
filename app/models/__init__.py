from .base import Base
from .user import User

# This ensures all models are loaded before create_all() is called
__all__ = ["Base", "User"]
