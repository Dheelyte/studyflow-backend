from .user import User
from .module import Module
from .playlist import Playlist
from .lesson import Lesson
from .resource import Resource
from .progress import UserModuleProgress, UserResourceProgress, UserPlaylist
from .community import Community
from .post import Post
from .comment import Comment
from .like import Like
from .activity import UserDailyActivity
from .quiz import Quiz
from .waitlist import Waitlist


# This ensures all models are loaded before create_all() is called
__all__ = [
    "User",
    "Playlist",
    "Module",
    "Lesson",
    "Resource",
    "Quiz",
    "UserModuleProgress",
    "UserResourceProgress",
    "UserPlaylist",
    "Community",
    "Post",
    "Comment",
    "Like",
    "UserDailyActivity",
    "Waitlist",
]
