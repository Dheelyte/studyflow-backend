from .user import User
from .module import Module
from .playlist import Playlist
from .resource import Resource


# This ensures all models are loaded before create_all() is called
__all__ = ["User", "Module", "Playlist", "Resource"]
