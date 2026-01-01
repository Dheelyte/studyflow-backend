from datetime import datetime, timezone

from typing import Annotated
from uuid import UUID
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.lesson import Lesson
from app.models.playlist import Playlist
from app.models.module import Module
from app.models.resource import Resource
from app.repositories.playlist import ModuleRepository, PlaylistRepository, LessonRepository, ResourceRepository
from app.schema.playlist import PlaylistCreate
from app.models.progress import UserPlaylistStatus, UserResourceProgress, UserModuleProgress, UserPlaylist


class PlaylistService:
    def __init__(
        self,
        playlist_repo: PlaylistRepository,
        module_repo: ModuleRepository,
        lesson_repo: LessonRepository,
        resource_repo: ResourceRepository,
        user_repo: UserRepository,
        activity_repo: ActivityRepository,
        streak_repo: StreakRepository,
        activity_service: ActivityService
    ):
        self.playlist_repo = playlist_repo
        self.module_repo = module_repo
        self.lesson_repo = lesson_repo
        self.resource_repo = resource_repo
        self.user_repo = user_repo
        self.activity_repo = activity_repo
        self.streak_repo = streak_repo
        self.activity_service = activity_service

    async def get_playlist(self, playlist_id: int, user_id: UUID):
        playlist = await self.playlist_repo.get_playlist_by_id(playlist_id)
        return playlist
    
    async def get_playlist_details(self, playlist_id: int, user_id: UUID):
        playlist = await self.playlist_repo.get_playlist_details(playlist_id, user_id)
        return playlist
    
    async def create_user_playlist(self, playlist_id: int, user_id: UUID):
        user_playlist = UserPlaylist(
            user_id=user_id,
            playlist_id=playlist_id,
        )
        await self.playlist_repo.add(user_playlist)
    
    async def get_user_playlists(self, user_id: UUID):
        playlists = await self.playlist_repo.get_user_playlists(user_id)
        return playlists

    async def create_playlist_from_curriculum(self, playlist_data: PlaylistCreate, user_id: UUID) -> Playlist:
        if playlist_data.content:
        # 1. Create Playlist Object
            new_playlist = Playlist(
                title=playlist_data.title,
                level=playlist_data.level,
                timeline=playlist_data.timeline,
                description=playlist_data.description,
                objectives=playlist_data.objectives,
                user_id=user_id,
            )
            new_playlist = await self.playlist_repo.add(new_playlist)
            
        # 2. Populate Modules and Resources if content is provided
        if playlist_data.content and 'modules' in playlist_data.content:
            modules_data = playlist_data.content['modules']
            for i, mod_data in enumerate(modules_data):
                new_module = Module(
                    title=mod_data.get('module_title', 'Untitled Module'),
                    description=mod_data.get('description', ''),
                    order=(i + 1),
                    playlist_id=new_playlist.id
                )
                new_module = await self.module_repo.add(new_module)
                lessons_data = mod_data.get('lessons', [])
                print(lessons_data)
                for j, les_data in enumerate(lessons_data):
                    new_lesson = Lesson(
                        title=les_data.get('lesson_title', 'Untitled Lesson'),
                        estimated_time=les_data.get('estimated_time', 'Untitle Estimation'),
                        module_id=new_module.id,
                        order=(j + 1)
                    )
                    new_lesson = await self.lesson_repo.add(new_lesson)
                    resources_data = les_data.get("resources")
                    for k, res_data in enumerate(resources_data):
                        new_resource = Resource(
                            title=res_data.get('label', 'Untitled Resource'),
                            url=res_data.get('resource_url', '#'),
                            type=res_data.get('type', 'article'),
                            description=res_data.get('description', 'Untitled Description'),
                            order=(k + 1),
                            lesson_id=new_lesson.id
                        )
                        await self.resource_repo.add(new_resource)
            
            await self.create_user_playlist(new_playlist.id, user_id)
        
        return new_playlist

    async def mark_resource_completed(self, resource_id: int, user_id: UUID):
        # Check if resource exists
        resource = await self.resource_repo.get_resource_by_id(resource_id)
        if not resource:
            return None
        
        # Get or create progress
        progress = await self.resource_repo.get_resource_progress(user_id, resource_id)
        now = datetime.now(timezone.utc)
        if progress:
            return progress

        progress = UserResourceProgress(
            user_id=user_id,
            resource_id=resource_id,
            is_completed=True,
            completed_at=now
        )
        await self.resource_repo.add(progress)

        # Activity Tracking Logic
        await self.activity_service.update_daily_activity(user_id)

        # Streak Tracking Logic
        await self.streak_repo.update_user_streak(user_id)
        
        # Gamification: Award XP
        user = await self.user_repo.get_by_id(user_id)
        if user:
            # Base completion XP provided by resource, defaulting to 10 if not implemented on model yet
            # Or constant base
            BASE_XP = 10 
            multiplier = 1 + (user.current_streak * 0.1)
            earned_xp = int(BASE_XP * multiplier)
            user.total_xp += earned_xp
            await self.user_repo.add(user)

        return progress


def get_playlist_repo(session: AsyncSession = Depends(get_session)):
    return PlaylistRepository(session)

def get_module_repo(session: AsyncSession = Depends(get_session)):
    return ModuleRepository(session)

def get_lesson_repo(session: AsyncSession = Depends(get_session)):
    return LessonRepository(session)

def get_resource_repo(session: AsyncSession = Depends(get_session)):
    return ResourceRepository(session)

def get_user_repo(session: AsyncSession = Depends(get_session)):
    return UserRepository(session)

def get_activity_repo(session: AsyncSession = Depends(get_session)):
    return ActivityRepository(session)

def get_streak_repo(session: AsyncSession = Depends(get_session)):
    return StreakRepository(session)

def get_playlist_service(
        playlist_repo: PlaylistRepository = Depends(get_playlist_repo),
        module_repo: ModuleRepository = Depends(get_module_repo),
        resource_repo: ResourceRepository = Depends(get_resource_repo),
        lesson_repo: LessonRepository = Depends(get_lesson_repo),
        user_repo: UserRepository = Depends(get_user_repo),
        activity_repo: ActivityRepository = Depends(get_activity_repo),
        streak_repo: StreakRepository = Depends(get_streak_repo),
        activity_service: ActivityService = Depends(get_activity_service)
    ):
    return PlaylistService(
        playlist_repo,
        module_repo,
        lesson_repo,
        resource_repo,
        user_repo,
        activity_repo,
        streak_repo,
        activity_service
    )

PlaylistServiceDep = Annotated[PlaylistService, Depends(get_playlist_service)]
