from uuid import UUID
from typing import Set
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import Module
from app.models.playlist import Playlist
from app.models.progress import UserPlaylist, UserResourceProgress
from app.models.resource import Resource
from app.models.user import User
from app.models.lesson import Lesson


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
        stmt = (
            select(UserPlaylist)
            .options(
                selectinload(UserPlaylist.playlist)
                .load_only(Playlist.id, Playlist.title)
            )
            .where(UserPlaylist.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        playlists = result.scalars().all()
        return playlists
    
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
            select(Module).where(Module.id == module_id)
        )
        module = result.scalar_one_or_none()
        return module
        

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