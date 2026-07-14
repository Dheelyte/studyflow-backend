from datetime import datetime, timezone

from typing import Annotated
from uuid import UUID
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..models.lesson import Lesson
from ..models.playlist import Playlist
from ..models.module import Module
from ..models.topic import Topic
from ..repositories.activity import ActivityRepository
from ..repositories.playlist import ModuleRepository, PlaylistRepository, LessonRepository, QuizRepository
from ..repositories.topic import TopicRepository
from ..repositories.streak import StreakRepository
from ..repositories.user import UserRepository
from ..schema.playlist import PlaylistCreate
from ..models.progress import UserTopicProgress, UserPlaylist
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
        topic_repo: TopicRepository,
        user_repo: UserRepository,
        activity_repo: ActivityRepository,
        streak_repo: StreakRepository,
        activity_service: ActivityService,
    ):
        self.playlist_repo = playlist_repo
        self.module_repo = module_repo
        self.lesson_repo = lesson_repo
        self.topic_repo = topic_repo
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
            user_playlist = record[0]  # UserPlaylist model
            total = record.total_topics
            completed = record.completed_topics

            percentage = 0.0
            if total > 0:
                percentage = (completed / total) * 100

            response = UserPlaylistResponse(
                id=user_playlist.id,
                user_id=user_playlist.user_id,
                created_at=user_playlist.created_at,
                playlist=ListPlaylistResponse(
                    id=user_playlist.playlist.id,
                    title=user_playlist.playlist.title,
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
                level="Beginner",
                timeline="",
                description=playlist_data.description,
                objectives=playlist_data.objectives,
                user_id=user_id,
            )
            new_playlist = await self.playlist_repo.add(new_playlist)

        # 2. Populate Modules, Lessons, and Topics if content is provided
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
                for j, les_data in enumerate(lessons_data):
                    new_lesson = Lesson(
                        title=les_data.get('lesson_title', 'Untitled Lesson'),
                        estimated_time=les_data.get('estimated_time', 'N/A'),
                        module_id=new_module.id,
                        order=(j + 1)
                    )
                    new_lesson = await self.lesson_repo.add(new_lesson)

                    # Create Topics (replaces Resources)
                    topics_data = les_data.get("topics", [])
                    for k, topic_data in enumerate(topics_data):
                        new_topic = Topic(
                            title=topic_data.get('title', 'Untitled Topic'),
                            description=topic_data.get('description', ''),
                            order=(k + 1),
                            lesson_id=new_lesson.id,
                            youtube_video_id=None,
                        )
                        await self.topic_repo.add(new_topic)

            await self.create_user_playlist(new_playlist.id, user_id)

        return new_playlist

    async def generate_module_quiz(
        self,
        module_id: int,
        curriculum_title: str,
    ) -> QuizBase | None:
        module = await self.module_repo.get_module_by_id(module_id)
        if not module:
            return None

        topic_titles = await self.module_repo.get_module_topic_titles(module_id)

        generated_quiz = await generate_quiz_response(
            curriculum_title=curriculum_title,
            experience_level="Beginner",
            topic_titles=topic_titles
        )
        return generated_quiz

    async def submit_quiz(self, module_id: int, submission: QuizSubmission, user_id: UUID) -> QuizSubmissionResponse | None:
        questions = submission.questions
        total_questions = len(questions)
        correct_count = 0

        question_map = {q.id: q for q in questions}

        for q_id, selected_option_id in submission.answers.items():
            if q_id in question_map:
                question = question_map[q_id]
                if question.correctOptionId == selected_option_id:
                    correct_count += 1

        score = (correct_count / total_questions) * 100 if total_questions > 0 else 0
        passed = score >= 70

        if passed:
            await self.module_repo.mark_module_quiz_completed(module_id, user_id)
            user = await self.user_repo.get_by_id(user_id)
            if user:
                BASE_XP = 50
                user.total_xp += BASE_XP
                await self.user_repo.add(user)

        return QuizSubmissionResponse(
            passed=passed
        )

    async def _check_and_update_module_progress(self, user_id: UUID, topic_id: int):
        """Check if all topics in a module are completed and update module progress."""
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            return

        lesson = await self.lesson_repo.get_lesson_by_id(topic.lesson_id)
        if not lesson:
            return

        module_id = lesson.module_id

        total_topics = await self.module_repo.get_module_topics_count(module_id)
        completed_topics = await self.module_repo.get_module_completed_topics_count(module_id, user_id)

        if completed_topics >= total_topics and total_topics > 0:
            await self.module_repo.mark_module_completed(module_id, user_id)

    async def mark_topic_completed(self, topic_id: int, user_id: UUID):
        """Mark a topic as completed and handle gamification."""
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            return None

        progress = await self.topic_repo.get_topic_progress(user_id, topic_id)
        now = datetime.now(timezone.utc)

        is_new_completion = False
        if not progress:
            is_new_completion = True
            progress = UserTopicProgress(
                user_id=user_id,
                topic_id=topic_id,
                is_completed=True,
                completed_at=now
            )
            await self.topic_repo.add(progress)
        elif not progress.is_completed:
            is_new_completion = True
            progress.is_completed = True
            progress.completed_at = now
            await self.topic_repo.add(progress)

        if is_new_completion:
            # Activity Tracking
            await self.activity_service.update_daily_activity(user_id)

            # Streak Tracking
            await self.streak_repo.update_user_streak(user_id)

            # Module Progress
            await self._check_and_update_module_progress(user_id, topic_id)

            # Gamification: Award XP
            user = await self.user_repo.get_by_id(user_id)
            if user:
                BASE_XP = 10
                multiplier = 1 + (user.current_streak * 0.1)
                earned_xp = int(BASE_XP * multiplier)
                user.total_xp += earned_xp
                await self.user_repo.add(user)

        return progress

    async def get_module_by_id(self, module_id: int):
        module = await self.module_repo.get_module_by_id(module_id)
        return module


def get_playlist_repo(session: AsyncSession = Depends(get_session)):
    return PlaylistRepository(session)

def get_module_repo(session: AsyncSession = Depends(get_session)):
    return ModuleRepository(session)

def get_lesson_repo(session: AsyncSession = Depends(get_session)):
    return LessonRepository(session)

def get_topic_repo(session: AsyncSession = Depends(get_session)):
    return TopicRepository(session)

def get_user_repo(session: AsyncSession = Depends(get_session)):
    from ..repositories.user import UserRepository
    return UserRepository(session)

def get_activity_repo(session: AsyncSession = Depends(get_session)):
    return ActivityRepository(session)

def get_streak_repo(session: AsyncSession = Depends(get_session)):
    return StreakRepository(session)


def get_playlist_service(
        playlist_repo: PlaylistRepository = Depends(get_playlist_repo),
        module_repo: ModuleRepository = Depends(get_module_repo),
        lesson_repo: LessonRepository = Depends(get_lesson_repo),
        topic_repo: TopicRepository = Depends(get_topic_repo),
        user_repo: UserRepository = Depends(get_user_repo),
        activity_repo: ActivityRepository = Depends(get_activity_repo),
        streak_repo: StreakRepository = Depends(get_streak_repo),
        activity_service: ActivityService = Depends(get_activity_service),
    ):
    return PlaylistService(
        playlist_repo,
        module_repo,
        lesson_repo,
        topic_repo,
        user_repo,
        activity_repo,
        streak_repo,
        activity_service
    )


PlaylistServiceDep = Annotated[PlaylistService, Depends(get_playlist_service)]
