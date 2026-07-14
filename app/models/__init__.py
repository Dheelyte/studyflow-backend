from .user import User
from .module import Module
from .playlist import Playlist
from .lesson import Lesson
from .resource import Resource
from .topic import Topic
from .progress import UserModuleProgress, UserResourceProgress, UserPlaylist, UserTopicProgress
from .community import Community
from .post import Post
from .comment import Comment
from .like import Like
from .activity import UserDailyActivity
from .quiz import Quiz
from .waitlist import Waitlist
from .chat import ChatSession, ChatMessage
from .certificate import Certificate


# This ensures all models are loaded before create_all() is called
__all__ = [
    "User",
    "Playlist",
    "Module",
    "Lesson",
    "Resource",
    "Topic",
    "Quiz",
    "UserModuleProgress",
    "UserResourceProgress",
    "UserTopicProgress",
    "UserPlaylist",
    "Community",
    "Post",
    "Comment",
    "Like",
    "UserDailyActivity",
    "Waitlist",
    "ChatSession",
    "ChatMessage",
    "Certificate",
]
