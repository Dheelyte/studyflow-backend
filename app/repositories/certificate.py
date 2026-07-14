from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.certificate import Certificate
from ..models.lesson import Lesson
from ..models.module import Module
from ..models.progress import UserModuleProgress, UserTopicProgress
from ..models.topic import Topic


class CertificateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_and_playlist(
        self, user_id: UUID, playlist_id: int
    ) -> Certificate | None:
        result = await self.session.execute(
            select(Certificate).where(
                Certificate.user_id == user_id,
                Certificate.playlist_id == playlist_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Certificate | None:
        result = await self.session.execute(
            select(Certificate).where(Certificate.verification_code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID) -> list[Certificate]:
        result = await self.session.execute(
            select(Certificate)
            .where(Certificate.user_id == user_id)
            .order_by(Certificate.issued_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, certificate: Certificate) -> Certificate:
        self.session.add(certificate)
        await self.session.flush()
        return certificate

    async def get_playlist_progress_counts(
        self, playlist_id: int, user_id: UUID
    ) -> tuple[int, int, int, int]:
        """Return (total_topics, completed_topics, total_modules, passed_quizzes)."""
        total_topics_stmt = (
            select(func.count(Topic.id))
            .join(Lesson, Lesson.id == Topic.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.playlist_id == playlist_id)
        )
        completed_topics_stmt = (
            select(func.count(UserTopicProgress.id))
            .join(Topic, Topic.id == UserTopicProgress.topic_id)
            .join(Lesson, Lesson.id == Topic.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(
                Module.playlist_id == playlist_id,
                UserTopicProgress.user_id == user_id,
                UserTopicProgress.is_completed == True,  # noqa: E712
            )
        )
        total_modules_stmt = (
            select(func.count(Module.id)).where(Module.playlist_id == playlist_id)
        )
        passed_quizzes_stmt = (
            select(func.count(UserModuleProgress.id))
            .join(Module, Module.id == UserModuleProgress.module_id)
            .where(
                Module.playlist_id == playlist_id,
                UserModuleProgress.user_id == user_id,
                UserModuleProgress.quiz_completed == True,  # noqa: E712
            )
        )

        total_topics = (await self.session.execute(total_topics_stmt)).scalar_one() or 0
        completed_topics = (
            await self.session.execute(completed_topics_stmt)
        ).scalar_one() or 0
        total_modules = (
            await self.session.execute(total_modules_stmt)
        ).scalar_one() or 0
        passed_quizzes = (
            await self.session.execute(passed_quizzes_stmt)
        ).scalar_one() or 0

        return total_topics, completed_topics, total_modules, passed_quizzes
