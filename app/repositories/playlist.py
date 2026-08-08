from uuid import UUID
from typing import Set
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import Module
from app.models.playlist import Playlist
from app.models.progress import UserPlaylist, UserTopicProgress, UserModuleProgress
from app.models.topic import Topic
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
        # Subquery for Total Topics per Playlist
        total_topics_sub = (
            select(
                Module.playlist_id,
                func.count(Topic.id).label('total_count')
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .join(Topic, Topic.lesson_id == Lesson.id)
            .group_by(Module.playlist_id)
            .subquery()
        )

        # Subquery for Completed Topics per Playlist for this User
        completed_topics_sub = (
            select(
                Module.playlist_id,
                func.count(UserTopicProgress.id).label('completed_count')
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .join(Topic, Topic.lesson_id == Lesson.id)
            .join(UserTopicProgress, (UserTopicProgress.topic_id == Topic.id) & (UserTopicProgress.user_id == user_id))
            .where(UserTopicProgress.is_completed == True)
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
                func.coalesce(total_topics_sub.c.total_count, 0).label('total_topics'),
                func.coalesce(completed_topics_sub.c.completed_count, 0).label('completed_topics'),
                func.coalesce(total_modules_sub.c.total_modules_count, 0).label('total_modules'),
                func.coalesce(completed_modules_sub.c.completed_modules_count, 0).label('completed_modules')
            )
            .options(
                selectinload(UserPlaylist.playlist)
                .load_only(Playlist.id, Playlist.title, Playlist.slug, Playlist.level)
            )
            .outerjoin(total_topics_sub, total_topics_sub.c.playlist_id == UserPlaylist.playlist_id)
            .outerjoin(completed_topics_sub, completed_topics_sub.c.playlist_id == UserPlaylist.playlist_id)
            .outerjoin(total_modules_sub, total_modules_sub.c.playlist_id == UserPlaylist.playlist_id)
            .outerjoin(completed_modules_sub, completed_modules_sub.c.playlist_id == UserPlaylist.playlist_id)
            .where(UserPlaylist.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def get_all_playlist_topics(self, playlist_id: int):
        stmt = (
            select(func.count(Topic.id))
            .join(Lesson, Lesson.id == Topic.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.playlist_id == playlist_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_user_playlist(self, playlist_id: int, user_id: int):
        result = await self.session.execute(
            select(UserPlaylist).where(
                UserPlaylist.user_id == user_id,
                UserPlaylist.playlist_id == playlist_id
            )
        )
        user_playlist = result.scalar_one_or_none()
        return user_playlist

    def _gallery_count_subqueries(self):
        """Module, lesson, topic and learner counts keyed by playlist_id, for gallery cards."""
        module_counts = (
            select(
                Module.playlist_id,
                func.count(Module.id).label('module_count')
            )
            .group_by(Module.playlist_id)
            .subquery()
        )

        lesson_counts = (
            select(
                Module.playlist_id,
                func.count(Lesson.id).label('lesson_count')
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .group_by(Module.playlist_id)
            .subquery()
        )

        topic_counts = (
            select(
                Module.playlist_id,
                func.count(Topic.id).label('topic_count')
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .join(Topic, Topic.lesson_id == Lesson.id)
            .group_by(Module.playlist_id)
            .subquery()
        )

        learner_counts = (
            select(
                UserPlaylist.playlist_id,
                func.count(UserPlaylist.id).label('learner_count')
            )
            .group_by(UserPlaylist.playlist_id)
            .subquery()
        )

        return module_counts, lesson_counts, topic_counts, learner_counts

    async def get_public_playlists(
        self,
        limit: int = 24,
        offset: int = 0,
        featured_only: bool = False,
        q: str | None = None,
    ):
        module_counts, lesson_counts, topic_counts, learner_counts = self._gallery_count_subqueries()

        learner_count_col = func.coalesce(learner_counts.c.learner_count, 0)

        stmt = (
            select(
                Playlist,
                func.coalesce(module_counts.c.module_count, 0).label('module_count'),
                func.coalesce(lesson_counts.c.lesson_count, 0).label('lesson_count'),
                func.coalesce(topic_counts.c.topic_count, 0).label('topic_count'),
                learner_count_col.label('learner_count'),
            )
            .options(
                selectinload(Playlist.author)
                .load_only(User.first_name, User.last_name)
            )
            .outerjoin(module_counts, module_counts.c.playlist_id == Playlist.id)
            .outerjoin(lesson_counts, lesson_counts.c.playlist_id == Playlist.id)
            .outerjoin(topic_counts, topic_counts.c.playlist_id == Playlist.id)
            .outerjoin(learner_counts, learner_counts.c.playlist_id == Playlist.id)
            .where(Playlist.is_public.is_(True), Playlist.slug.isnot(None))
            .order_by(
                Playlist.is_featured.desc(),
                learner_count_col.desc(),
                Playlist.published_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        if featured_only:
            stmt = stmt.where(Playlist.is_featured.is_(True))

        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                Playlist.title.ilike(pattern) | Playlist.description.ilike(pattern)
            )

        result = await self.session.execute(stmt)
        return result.all()

    async def get_public_playlist_by_slug(self, slug: str):
        """Full nested outline for a published course. Returns None if not public."""
        stmt = (
            select(Playlist)
            .options(
                selectinload(Playlist.modules)
                .selectinload(Module.lessons)
                .selectinload(Lesson.topics),
                selectinload(Playlist.author)
                .load_only(User.first_name, User.last_name),
            )
            .where(Playlist.slug == slug, Playlist.is_public.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_playlist_counts(self, playlist_id: int):
        """(module_count, lesson_count, topic_count, learner_count) for a single playlist."""
        module_counts, lesson_counts, topic_counts, learner_counts = self._gallery_count_subqueries()

        stmt = (
            select(
                func.coalesce(module_counts.c.module_count, 0),
                func.coalesce(lesson_counts.c.lesson_count, 0),
                func.coalesce(topic_counts.c.topic_count, 0),
                func.coalesce(learner_counts.c.learner_count, 0),
            )
            .select_from(Playlist)
            .outerjoin(module_counts, module_counts.c.playlist_id == Playlist.id)
            .outerjoin(lesson_counts, lesson_counts.c.playlist_id == Playlist.id)
            .outerjoin(topic_counts, topic_counts.c.playlist_id == Playlist.id)
            .outerjoin(learner_counts, learner_counts.c.playlist_id == Playlist.id)
            .where(Playlist.id == playlist_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return row if row else (0, 0, 0, 0)

    async def get_public_playlist_id_by_slug(self, slug: str) -> int | None:
        stmt = (
            select(Playlist.id)
            .where(Playlist.slug == slug, Playlist.is_public.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_playlist_id(self, ref: str) -> int | None:
        """Accept either a numeric id or a slug, so old numeric URLs keep working."""
        if isinstance(ref, int):
            return ref
        if isinstance(ref, str) and ref.isdigit():
            return int(ref)

        stmt = select(Playlist.id).where(Playlist.slug == ref)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        stmt = select(Playlist.id).where(Playlist.slug == slug).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_public_slugs(self, limit: int = 1000):
        stmt = (
            select(Playlist.slug, Playlist.published_at)
            .where(Playlist.is_public.is_(True), Playlist.slug.isnot(None))
            .order_by(Playlist.published_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def get_playlist_details(self, playlist_id: int, user_id: UUID):
        # 1. Fetch Playlist with nested data (modules → lessons → topics)
        stmt = (
            select(Playlist)
            .options(
                selectinload(Playlist.modules)
                .selectinload(Module.lessons)
                .selectinload(Lesson.topics)
            )
            .where(Playlist.id == playlist_id)
        )
        result = await self.session.execute(stmt)
        playlist = result.scalar_one_or_none()

        if not playlist:
            return None

        # 2. Fetch User's Completed Topics for this playlist
        progress_stmt = (
            select(UserTopicProgress.topic_id)
            .join(Topic)
            .join(Lesson)
            .join(Module)
            .where(
                Module.playlist_id == playlist_id,
                UserTopicProgress.user_id == user_id,
                UserTopicProgress.is_completed == True
            )
        )
        progress_result = await self.session.execute(progress_stmt)
        completed_topic_ids: Set[int] = set(progress_result.scalars().all())

        # 3. Fetch User's Module Progress (for quiz_completed)
        module_progress_stmt = (
            select(UserModuleProgress.module_id)
            .join(Module)
            .where(
                Module.playlist_id == playlist_id,
                UserModuleProgress.user_id == user_id,
                UserModuleProgress.quiz_completed == True
            )
        )
        module_progress_result = await self.session.execute(module_progress_stmt)
        quiz_completed_module_ids: Set[int] = set(module_progress_result.scalars().all())

        # 4. Attach progress to topics and modules (in memory)
        for module in playlist.modules:
            setattr(module, 'quiz_completed', module.id in quiz_completed_module_ids)
            for lesson in module.lessons:
                for topic in lesson.topics:
                    setattr(topic, 'is_completed', topic.id in completed_topic_ids)

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

    async def get_module_topics_count(self, module_id: int) -> int:
        """Count total topics in a module across all its lessons."""
        stmt = (
            select(func.count(Topic.id))
            .join(Lesson)
            .where(Lesson.module_id == module_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_module_topic_titles(self, module_id: int) -> list[str]:
        """Return all topic titles inside a module, ordered by lesson and topic order."""
        stmt = (
            select(Topic.title)
            .join(Lesson)
            .where(Lesson.module_id == module_id)
            .order_by(Lesson.order, Topic.order)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_module_completed_topics_count(self, module_id: int, user_id: UUID) -> int:
        """Count completed topics in a module for a user."""
        stmt = (
            select(func.count(UserTopicProgress.id))
            .join(Topic)
            .join(Lesson)
            .where(
                Lesson.module_id == module_id,
                UserTopicProgress.user_id == user_id,
                UserTopicProgress.is_completed == True
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def mark_module_completed(self, module_id: int, user_id: UUID) -> UserModuleProgress:
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

        new_progress = UserModuleProgress(
            user_id=user_id,
            module_id=module_id,
            is_completed=True
        )
        self.session.add(new_progress)
        await self.session.flush()
        return new_progress

    async def mark_module_quiz_completed(self, module_id: int, user_id: UUID) -> UserModuleProgress:
        stmt = select(UserModuleProgress).where(
            UserModuleProgress.user_id == user_id,
            UserModuleProgress.module_id == module_id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if not existing.quiz_completed:
                existing.quiz_completed = True
                await self.session.flush()
            return existing

        new_progress = UserModuleProgress(
            user_id=user_id,
            module_id=module_id,
            quiz_completed=True
        )
        self.session.add(new_progress)
        await self.session.flush()
        return new_progress


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


class QuizRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_quiz_by_module_id(self, module_id: int) -> Quiz | None:
        stmt = select(Quiz).where(Quiz.module_id == module_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
