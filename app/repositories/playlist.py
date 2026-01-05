from uuid import UUID
from typing import Set
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import Module
from app.models.playlist import Playlist
from app.models.progress import UserPlaylist, UserResourceProgress, UserModuleProgress
from app.models.resource import Resource
from app.models.user import User
from app.models.lesson import Lesson
from app.models.quiz import Quiz


class PlaylistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add(self, playlist_model):
        self.session.add(playlist_model)
        await self.session.flush()
        return playlist_model
    
    async def get_playlist_by_id(self, playlist_id: int):
        stmt = (
            select(Playlist)
            .where(Playlist.id == playlist_id)
        )
        result = await self.session.execute(stmt)
        playlist = result.scalar_one_or_none()
        return playlist
    
    async def get_user_playlists(self, user_id: UUID):
        # Subquery for Total Resources per Playlist
        total_resources_sub = (
            select(
                Module.playlist_id,
                func.count(Resource.id).label('total_count')
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .join(Resource, Resource.lesson_id == Lesson.id)
            .group_by(Module.playlist_id)
            .subquery()
        )

        # Subquery for Completed Resources per Playlist for this User
        completed_resources_sub = (
            select(
                Module.playlist_id,
                func.count(UserResourceProgress.id).label('completed_count')
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .join(Resource, Resource.lesson_id == Lesson.id)
            .join(UserResourceProgress, (UserResourceProgress.resource_id == Resource.id) & (UserResourceProgress.user_id == user_id))
            .where(UserResourceProgress.is_completed == True)
            .group_by(Module.playlist_id)
            .subquery()
        )

        # Subquery for Total Modules per Playlist
        total_modules_sub = (
            select(
                Module.playlist_id,
                func.count(Module.id).label('total_modules_count')
            )
            .group_by(Module.playlist_id)
            .subquery()
        )

        # Subquery for Completed Modules per Playlist for this User
        completed_modules_sub = (
            select(
                Module.playlist_id,
                func.count(UserModuleProgress.id).label('completed_modules_count')
            )
            .join(UserModuleProgress, UserModuleProgress.module_id == Module.id)
            .where(
                UserModuleProgress.user_id == user_id,
                UserModuleProgress.is_completed == True
            )
            .group_by(Module.playlist_id)
            .subquery()
        )

        stmt = (
            select(
                UserPlaylist,
                func.coalesce(total_resources_sub.c.total_count, 0).label('total_resources'),
                func.coalesce(completed_resources_sub.c.completed_count, 0).label('completed_resources'),
                func.coalesce(total_modules_sub.c.total_modules_count, 0).label('total_modules'),
                func.coalesce(completed_modules_sub.c.completed_modules_count, 0).label('completed_modules')
            )
            .options(
                selectinload(UserPlaylist.playlist)
                .load_only(Playlist.id, Playlist.title)
            )
            .outerjoin(total_resources_sub, total_resources_sub.c.playlist_id == UserPlaylist.playlist_id)
            .outerjoin(completed_resources_sub, completed_resources_sub.c.playlist_id == UserPlaylist.playlist_id)
            .outerjoin(total_modules_sub, total_modules_sub.c.playlist_id == UserPlaylist.playlist_id)
            .outerjoin(completed_modules_sub, completed_modules_sub.c.playlist_id == UserPlaylist.playlist_id)
            .where(UserPlaylist.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.all()
    
    async def get_all_playlist_resources(self, playlist_id: int):
        stmt = (
            select(func.count(Resource.id))
            .join(Module)
            .where(Module.playlist_id == playlist_id)
        )
        result = await self.session.execute(stmt)
        total_resources = result.scalar_one()
        return total_resources
    
    async def get_completed_resource_count(self, playlist_id: int, user_id: UUID):
        stmt = (
            select(func.count(UserResourceProgress.id))
            .join(Resource)
            .join(Module)
            .where(
                Module.playlist_id == playlist_id,
                UserResourceProgress.user_id == user_id,
                UserResourceProgress.is_completed == True
            )
        )
        result = await self.session.execute(stmt)
        completed_resources = result.scalar_one()
        return completed_resources
    
    async def get_user_playlist(self, playlist_id: int, user_id: int):
        result = await self.session.execute(
            select(UserPlaylist).where(
                UserPlaylist.user_id == user_id,
                UserPlaylist.playlist_id == playlist_id
            )
        )
        user_playlist = result.scalar_one_or_none()
        return user_playlist

    async def get_playlist_details(self, playlist_id: int, user_id: UUID):
        # 1. Fetch Playlist with nested data
        stmt = (
            select(Playlist)
            .options(
                selectinload(Playlist.modules)
                .selectinload(Module.lessons)
                .selectinload(Lesson.resources)
            )
            .where(Playlist.id == playlist_id)
        )
        result = await self.session.execute(stmt)
        playlist = result.scalar_one_or_none()
        
        if not playlist:
            return None

        # 2. Fetch User's Completed Resources for this playlist
        # This avoids N+1 queries for progress
        progress_stmt = (
            select(UserResourceProgress.resource_id)
            .join(Resource)
            .join(Lesson)
            .join(Module)
            .where(
                Module.playlist_id == playlist_id,
                UserResourceProgress.user_id == user_id,
                UserResourceProgress.is_completed == True
            )
        )
        progress_result = await self.session.execute(progress_stmt)
        completed_resource_ids: Set[int] = set(progress_result.scalars().all())

        # 3. Attach progress to resources (in memory)
        # We perform a traversal to set the is_completed flag
        # Pydantic schema will pick this up if the attribute exists
        for module in playlist.modules:
            for lesson in module.lessons:
                for resource in lesson.resources:
                    # Dynamically set attribute - SQLAlchemy models are Python objects
                    setattr(resource, 'is_completed', resource.id in completed_resource_ids)
        
        return playlist


class ModuleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, module: Module):
        self.session.add(module)
        await self.session.flush()
        return module
    
    async def get_module_by_id(self, module_id: int):
        result = await self.session.execute(
            select(Module)
            .where(Module.id == module_id)
        )
        module = result.scalar_one_or_none()
        return module
    
    async def get_module_resources_count(self, module_id: int) -> int:
        stmt = (
            select(func.count(Resource.id))
            .join(Lesson)
            .where(Lesson.module_id == module_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_module_completed_resources_count(self, module_id: int, user_id: UUID) -> int:
        stmt = (
            select(func.count(UserResourceProgress.id))
            .join(Resource)
            .join(Lesson)
            .where(
                Lesson.module_id == module_id,
                UserResourceProgress.user_id == user_id,
                UserResourceProgress.is_completed == True
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def mark_module_completed(self, module_id: int, user_id: UUID) -> UserModuleProgress:
        # Check if already completed
        stmt = select(UserModuleProgress).where(
            UserModuleProgress.user_id == user_id,
            UserModuleProgress.module_id == module_id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            if not existing.is_completed:
                existing.is_completed = True
                await self.session.flush()
            return existing
        
        # Create new
        new_progress = UserModuleProgress(
            user_id=user_id,
            module_id=module_id,
            is_completed=True
        )
        self.session.add(new_progress)
        await self.session.flush()
        return new_progress
        

class ResourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, resource_model):
        self.session.add(resource_model)
        await self.session.flush()
        return resource_model

    async def get_resource_by_id(self, resource_id: int):
        result = await self.session.execute(select(Resource).where(Resource.id == resource_id))
        resource = result.scalar_one_or_none()
        return resource
    
    async def get_resource_progress(self, user_id, resource_id):
        result = await self.session.execute(
            select(UserResourceProgress).where(
                UserResourceProgress.user_id == user_id,
                UserResourceProgress.resource_id == resource_id
            )
        )
        progress = result.scalar_one_or_none()
        return progress
    
    
class LessonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, lesson_model):
        self.session.add(lesson_model)
        await self.session.flush()
        return lesson_model

    async def get_lesson_by_id(self, lesson_id: int):
        result = await self.session.execute(select(Lesson).where(Lesson.id == lesson_id))
        lesson = result.scalar_one_or_none()
        return lesson
    
    async def get_resource_progress(self, user_id, lesson_id):
        result = await self.session.execute(
            select(UserResourceProgress).where(
                UserResourceProgress.user_id == user_id,
                UserResourceProgress.resource_id == lesson_id
            )
        )
        progress = result.scalar_one_or_none()
        return progress


class QuizRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_quiz_by_module_id(self, module_id: int) -> Quiz | None:
        stmt = select(Quiz).where(Quiz.module_id == module_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
