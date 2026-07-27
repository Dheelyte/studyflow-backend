from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson import Lesson
from app.models.module import Module
from app.models.playlist import Playlist
from app.models.project import Project, UserProjectProgress
from app.models.topic import Topic


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, model):
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_capstone(self, playlist_id: int) -> Project | None:
        stmt = select(Project).where(
            Project.playlist_id == playlist_id,
            Project.module_id.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_module_project(self, module_id: int) -> Project | None:
        stmt = select(Project).where(Project.module_id == module_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_project_by_id(self, project_id: int) -> Project | None:
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_progress(self, user_id: UUID, project_id: int) -> UserProjectProgress | None:
        stmt = select(UserProjectProgress).where(
            UserProjectProgress.user_id == user_id,
            UserProjectProgress.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_playlist(self, playlist_id: int) -> Playlist | None:
        stmt = select(Playlist).where(Playlist.id == playlist_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_module(self, module_id: int) -> Module | None:
        stmt = select(Module).where(Module.id == module_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_playlist_topic_titles(self, playlist_id: int, limit: int = 60) -> list[str]:
        """Topic titles across the whole course, for capstone context."""
        stmt = (
            select(Topic.title)
            .join(Lesson, Lesson.id == Topic.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.playlist_id == playlist_id)
            .order_by(Module.order, Lesson.order, Topic.order)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_module_topic_titles(self, module_id: int) -> list[str]:
        stmt = (
            select(Topic.title)
            .join(Lesson, Lesson.id == Topic.lesson_id)
            .where(Lesson.module_id == module_id)
            .order_by(Lesson.order, Topic.order)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]
