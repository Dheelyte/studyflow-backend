from datetime import date, timezone, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson import Lesson
from app.models.module import Module
from app.models.playlist import Playlist
from app.models.project import Project
from app.models.screen_tutor import ScreenTutorUsage
from app.models.topic import Topic


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


class ScreenTutorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_usage(self, user_id: UUID, day: date | None = None) -> ScreenTutorUsage | None:
        stmt = select(ScreenTutorUsage).where(
            ScreenTutorUsage.user_id == user_id,
            ScreenTutorUsage.usage_date == (day or today_utc()),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_usage(self, user_id: UUID) -> ScreenTutorUsage:
        usage = await self.get_usage(user_id)
        if usage:
            usage.question_count += 1
        else:
            usage = ScreenTutorUsage(
                user_id=user_id, usage_date=today_utc(), question_count=1
            )
            self.session.add(usage)
        await self.session.flush()
        return usage

    async def get_topic_context(self, topic_id: int) -> dict:
        """Topic -> lesson -> module -> course, in one hop, for prompt context."""
        stmt = (
            select(
                Topic.title,
                Topic.description,
                Module.title,
                Playlist.title,
            )
            .join(Lesson, Lesson.id == Topic.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .join(Playlist, Playlist.id == Module.playlist_id)
            .where(Topic.id == topic_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if not row:
            return {}
        return {
            "topic_title": row[0],
            "topic_description": row[1],
            "module_title": row[2],
            "course_title": row[3],
        }

    async def get_pin_targets(self, playlist_id: int):
        """Lessons and already-generated projects the learner can point the tutor at.

        Projects are listed only if they already exist , this must never trigger
        brief generation as a side effect of opening a dropdown.
        """
        topics_stmt = (
            select(Topic.id, Topic.title, Module.title)
            .join(Lesson, Lesson.id == Topic.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.playlist_id == playlist_id)
            .order_by(Module.order, Lesson.order, Topic.order)
        )
        topics = (await self.session.execute(topics_stmt)).all()

        projects_stmt = (
            select(Project.id, Project.title, Project.module_id)
            .where(Project.playlist_id == playlist_id)
            .order_by(Project.module_id.nulls_first())
        )
        projects = (await self.session.execute(projects_stmt)).all()

        course_stmt = select(Playlist.title).where(Playlist.id == playlist_id)
        course_title = (await self.session.execute(course_stmt)).scalar_one_or_none()

        return course_title, topics, projects

    async def get_project_context(self, project_id: int) -> dict:
        stmt = select(Project.title, Project.summary).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        row = result.first()
        if not row:
            return {}
        return {"project_title": row[0], "project_summary": row[1]}
