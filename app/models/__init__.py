from .user import User
# from .module import Module
# from .playlist import Playlist
# from .resource import Resource
from .community import Community
from .post import Post
from .comment import Comment


# This ensures all models are loaded before create_all() is called
__all__ = ["User", "Community", "Post", "Comment"]
