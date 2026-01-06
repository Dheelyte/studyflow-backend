from datetime import datetime, timezone

from typing import Annotated
from uuid import UUID
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..models.lesson import Lesson
from ..models.playlist import Playlist
from ..models.module import Module
from ..models.resource import Resource
from ..repositories.activity import ActivityRepository
from ..repositories.playlist import ModuleRepository, PlaylistRepository, LessonRepository, ResourceRepository, QuizRepository
from ..repositories.streak import StreakRepository
from ..repositories.user import UserRepository
from ..schema.playlist import PlaylistCreate
from ..models.progress import UserResourceProgress, UserPlaylist
from ..schema.progress import UserPlaylistResponse, PlaylistProgress, ListPlaylistResponse
from ..services.activity import ActivityService, get_activity_service
from ..schema.quiz import QuizSubmission, QuizSubmissionResponse, QuizBase
from ..chains.generate_quiz import generate_quiz_response


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
        activity_service: ActivityService,
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
        playlist_records = await self.playlist_repo.get_user_playlists(user_id)
        
        results = []
        for record in playlist_records:
            user_playlist = record[0] # UserPlaylist model
            total = record.total_resources
            completed = record.completed_resources
            
            # Calculate percentage
            percentage = 0.0
            if total > 0:
                percentage = (completed / total) * 100
                
            # Create response object manually since we're enriching it
            response = UserPlaylistResponse(
                id=user_playlist.id,
                user_id=user_playlist.user_id,
                created_at=user_playlist.created_at,
                playlist=ListPlaylistResponse(
                    id=user_playlist.playlist.id,
                    title=user_playlist.playlist.title
                ),
                progress=PlaylistProgress(
                    completed_modules=record.completed_modules,
                    total_modules=record.total_modules,
                    percentage=round(percentage, 1)
                )
            )
            results.append(response)
            
        return results

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
                module_topics_covered = []
                new_module = Module(
                    title=mod_data.get('module_title', 'Untitled Module'),
                    description=mod_data.get('description', ''),
                    topics_covered=[],
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
                    module_topics_covered.extend(les_data.get('topics_covered', []))
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
                new_module.topics_covered = module_topics_covered
                await self.module_repo.add(new_module)
            
            await self.create_user_playlist(new_playlist.id, user_id)
            
        
        return new_playlist

    async def generate_module_quiz(
        self,
        module_id: int,
        curriculum_title: str,
        experience_level: str
    ) -> QuizBase | None:
        # Stateless: Generate Only
        module = await self.module_repo.get_module_by_id(module_id)
        if not module:
             return None
             
        generated_quiz = await generate_quiz_response(
            curriculum_title=curriculum_title,
            experience_level=experience_level,
            topics_covered=module.topics_covered
        )
        return generated_quiz

    async def submit_quiz(self, module_id: int, submission: QuizSubmission, user_id: UUID) -> QuizSubmissionResponse | None:
        # Stateless Verification
        questions = submission.questions
        total_questions = len(questions)
        correct_count = 0
        
        # Map question ID to question for easier lookup
        question_map = {q.id: q for q in questions}
        
        for q_id, selected_option_id in submission.answers.items():
            if q_id in question_map:
                question = question_map[q_id]
                # Check correctness
                if question.correctOptionId == selected_option_id:
                    correct_count += 1
                    
        score = (correct_count / total_questions) * 100 if total_questions > 0 else 0
        passed = score >= 70 
        
        if passed:
            await self.module_repo.mark_module_quiz_completed(module_id, user_id)
            # Gamification: Award XP for Quiz
            # Logic similar to resource completion
            user = await self.user_repo.get_by_id(user_id)
            if user:
                 BASE_XP = 50 # Bigger reward for quiz
                 user.total_xp += BASE_XP
                 await self.user_repo.add(user)

        return QuizSubmissionResponse(
            passed=passed
        )

    async def _check_and_update_module_progress(self, user_id: UUID, resource_id: int):
        # 1. Get Resource to find Lesson -> Module
        resource = await self.resource_repo.get_resource_by_id(resource_id)
        if not resource: 
            return # Should exist
        
        lesson = await self.lesson_repo.get_lesson_by_id(resource.lesson_id)
        if not lesson:
            return
            
        module_id = lesson.module_id
        
        # 2. Check counts
        total_resources = await self.module_repo.get_module_resources_count(module_id)
        completed_resources = await self.module_repo.get_module_completed_resources_count(module_id, user_id)
        
        if completed_resources >= total_resources and total_resources > 0:
            await self.module_repo.mark_module_completed(module_id, user_id)

    async def mark_resource_completed(self, resource_id: int, user_id: UUID):
        # Check if resource exists
        resource = await self.resource_repo.get_resource_by_id(resource_id)
        if not resource:
            return None
        
        # Get or create progress
        progress = await self.resource_repo.get_resource_progress(user_id, resource_id)
        now = datetime.now(timezone.utc)
        
        is_new_completion = False
        if not progress:
            is_new_completion = True
            progress = UserResourceProgress(
                user_id=user_id,
                resource_id=resource_id,
                is_completed=True,
                completed_at=now
            )
            await self.resource_repo.add(progress)
        elif not progress.is_completed:
            is_new_completion = True
            progress.is_completed = True
            progress.completed_at = now
            # Assume add/flush handles update
            await self.resource_repo.add(progress)

        if is_new_completion:
            # Activity Tracking Logic
            await self.activity_service.update_daily_activity(user_id)

            # Streak Tracking Logic
            await self.streak_repo.update_user_streak(user_id)
            
            # Module Progress Logic
            await self._check_and_update_module_progress(user_id, resource_id)
            
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

    async def get_module_by_id(self, module_id: int):
        module = await self.module_repo.get_module_by_id(module_id)
        return module

    
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
        activity_service: ActivityService = Depends(get_activity_service),
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
