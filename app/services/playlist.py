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
from app.repositories.user import UserRepository
from app.schema.playlist import PlaylistCreate
from app.models.progress import UserPlaylistStatus, UserResourceProgress, UserModuleProgress, UserPlaylist


class PlaylistService:
    def __init__(
        self,
        playlist_repo: PlaylistRepository,
        module_repo: ModuleRepository,
        lesson_repo: LessonRepository,
        resource_repo: ResourceRepository,
        user_repo: UserRepository
    ):
        self.playlist_repo = playlist_repo
        self.module_repo = module_repo
        self.lesson_repo = lesson_repo
        self.resource_repo = resource_repo
        self.user_repo = user_repo

    async def get_playlist(self, playlist_id: int):
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
                title=playlist_data.content["curriculum_title"],
                content=playlist_data.content,
                level=playlist_data.level,
                timeline=playlist_data.timeline,
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
    
    async def update_resource_status(self, resource_id: int, user_id: int):
        # Check if resource exists
        resource = await self.resource_repo.get_resource_by_id(resource_id)
        if not resource:
            return None # Or raise exception, handled by caller
        # Get or create progress
        progress = await self.resource_repo.get_resource_progress(user_id, resource_id)
        if progress:
            progress.is_completed = not progress.is_completed
            progress.completed_at = datetime.now(timezone.utc) if progress.is_completed else None
        else:
            progress = UserResourceProgress(
                user_id=user_id,
                resource_id=resource_id,
                is_completed=True,
                completed_at=datetime.now(timezone.utc)
            )
            await self.resource_repo.add(progress)

        # Check parent module/playlist progress
        # await self._check_playlist_progress(user_id, resource.lesson_id)
        return progress

    async def mark_resource_completed(self, resource_id: int, user_id: UUID):
        # Check if resource exists
        resource = await self.resource_repo.get_resource_by_id(resource_id)
        if not resource:
            return None
        
        # Get or create progress
        progress = await self.resource_repo.get_resource_progress(user_id, resource_id)
        if not progress:
            progress = UserResourceProgress(
                user_id=user_id,
                resource_id=resource_id,
                is_completed=True,
                completed_at=datetime.now(timezone.utc)
            )
            await self.resource_repo.add(progress)
        elif not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = datetime.now(timezone.utc)
        
        # Streak Logic
        user = await self.user_repo.get_by_id(user_id)
        if user:
            now = datetime.now(timezone.utc)
            today_date = now.date()
            
            last_active = user.last_active_date
            if last_active:
                last_active_date = last_active.date()
                delta_days = (today_date - last_active_date).days
                
                if delta_days == 1:
                    # Consecutive day
                    user.current_streak += 1
                elif delta_days > 1:
                    # Broken streak
                    user.current_streak = 1
                # If delta_days == 0 (same day), do nothing
            else:
                # First activity
                user.current_streak = 1
            
            # Update longest streak
            if user.current_streak > user.longest_streak:
                user.longest_streak = user.current_streak
                
            user.last_active_date = now
            # await self.user_repo.add(user) # Save changes

        return progress
    
    # async def _check_playlist_progress(self, user_id: int, module_id: int):
    #     # Find playlist_id from module
    #     module = await self.module_repo.get_module_by_id(module_id)
    #     if not module:
    #         return
    #     playlist_id = module.playlist_id
        
    #     # Check all modules in playlist
    #     # Ideally checking resources is more granular/accurate
    #     # Strategy: Get all resources for this playlist
    #     # Check if a UserResourceProgress exists and is_completed for ALL resources
        
    #     # 1. Get total resource count
    #     total_resources = await self.playlist_repo.get_all_playlist_resources()
    #     if total_resources == 0:
    #         return # Empty playlist
    #     # 2. Get completed resource count for user
    #     completed_resources = await self.playlist_repo.get_completed_resource_count(
    #         playlist_id, user_id
    #     )
    #     # Update UserPlaylist status
    #     user_playlist = await self.playlist_repo.get_user_playlist(user_playlist)
    #     new_status = UserPlaylistStatus.COMPLETED if completed_resources >= total_resources else UserPlaylistStatus.ACTIVE
    #     if user_playlist:
    #         user_playlist.status = new_status
        # else:
        #     user_playlist = UserPlaylist(
        #         user_id=user_id,
        #         playlist_id=playlist_id,
        #         status=new_status,
        #         joined_at=datetime.now(timezone.utc)
        #     )
        #     self.playlist_repo.add(user_playlist)


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

def get_playlist_service(
        playlist_repo: PlaylistRepository = Depends(get_playlist_repo),
        module_repo: ModuleRepository = Depends(get_module_repo),
        resource_repo: ResourceRepository = Depends(get_resource_repo),
        lesson_repo: LessonRepository = Depends(get_lesson_repo),
        user_repo: UserRepository = Depends(get_user_repo)
    ):
    return PlaylistService(playlist_repo, module_repo, lesson_repo, resource_repo, user_repo)

PlaylistServiceDep = Annotated[PlaylistService, Depends(get_playlist_service)]
