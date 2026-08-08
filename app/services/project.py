from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..chains.generate_project import generate_project_response
from ..db.session import get_session
from ..exceptions.base import BadRequestError, NotFoundError
from ..models.project import Project, UserProjectProgress
from ..repositories.activity import ActivityRepository
from ..repositories.project import ProjectRepository
from ..repositories.streak import StreakRepository
from ..repositories.user import UserRepository
from ..schema.project import (
    ProjectProgressRead,
    ProjectProgressUpdate,
    ProjectRead,
    ProjectSummary,
)
from ..services.activity import ActivityService, get_activity_service

CAPSTONE_XP = 250
PRACTICE_XP = 75


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        user_repo: UserRepository,
        streak_repo: StreakRepository,
        activity_service: ActivityService,
    ):
        self.project_repo = project_repo
        self.user_repo = user_repo
        self.streak_repo = streak_repo
        self.activity_service = activity_service

    @staticmethod
    def xp_reward(project: Project) -> int:
        return CAPSTONE_XP if project.module_id is None else PRACTICE_XP

    def _to_read(self, project: Project, progress: UserProjectProgress | None) -> ProjectRead:
        return ProjectRead(
            id=project.id,
            playlist_id=project.playlist_id,
            module_id=project.module_id,
            is_capstone=project.module_id is None,
            title=project.title,
            summary=project.summary,
            brief=project.brief,
            estimated_time=project.estimated_time,
            requirements=project.requirements or [],
            xp_reward=self.xp_reward(project),
            progress=(
                ProjectProgressRead.model_validate(progress)
                if progress
                else ProjectProgressRead()
            ),
        )

    async def _persist_brief(
        self, playlist_id: int, module_id: int | None, brief
    ) -> Project:
        project = Project(
            playlist_id=playlist_id,
            module_id=module_id,
            title=brief.title,
            summary=brief.summary,
            brief=brief.brief,
            estimated_time=brief.estimated_time or "",
            requirements=[r.model_dump() for r in brief.requirements],
        )
        return await self.project_repo.add(project)

    async def get_or_create_capstone(self, playlist_id: int, user_id: UUID) -> ProjectRead:
        """Briefs are generated on first open and then reused by every learner."""
        project = await self.project_repo.get_capstone(playlist_id)

        if not project:
            playlist = await self.project_repo.get_playlist(playlist_id)
            if not playlist:
                raise NotFoundError("Course not found")

            topics = await self.project_repo.get_playlist_topic_titles(playlist_id)
            brief = await generate_project_response(
                course_title=playlist.title,
                covered_topics=topics,
                is_capstone=True,
            )
            if not brief:
                raise BadRequestError("Could not generate a project right now. Please try again.")

            project = await self._persist_brief(playlist_id, None, brief)

        progress = await self.project_repo.get_progress(user_id, project.id)
        return self._to_read(project, progress)

    async def get_or_create_module_project(self, module_id: int, user_id: UUID) -> ProjectRead:
        project = await self.project_repo.get_module_project(module_id)

        if not project:
            module = await self.project_repo.get_module(module_id)
            if not module:
                raise NotFoundError("Module not found")

            playlist = await self.project_repo.get_playlist(module.playlist_id)
            topics = await self.project_repo.get_module_topic_titles(module_id)
            brief = await generate_project_response(
                course_title=playlist.title if playlist else module.title,
                covered_topics=topics,
                is_capstone=False,
                module_title=module.title,
            )
            if not brief:
                raise BadRequestError("Could not generate a project right now. Please try again.")

            project = await self._persist_brief(module.playlist_id, module_id, brief)

        progress = await self.project_repo.get_progress(user_id, project.id)
        return self._to_read(project, progress)

    async def get_capstone_summary(self, playlist_id: int) -> ProjectSummary | None:
        """Public teaser. Never generates , an anonymous visitor must not trigger an LLM call."""
        project = await self.project_repo.get_capstone(playlist_id)
        if not project:
            return None
        return ProjectSummary(
            title=project.title,
            summary=project.summary,
            estimated_time=project.estimated_time,
        )

    async def update_progress(
        self, project_id: int, user_id: UUID, payload: ProjectProgressUpdate
    ) -> ProjectRead:
        project = await self.project_repo.get_project_by_id(project_id)
        if not project:
            raise NotFoundError("Project not found")

        valid_ids = {r.get("id") for r in (project.requirements or [])}

        progress = await self.project_repo.get_progress(user_id, project_id)
        if not progress:
            progress = UserProjectProgress(
                user_id=user_id,
                project_id=project_id,
                completed_requirement_ids=[],
            )
            await self.project_repo.add(progress)

        if payload.completed_requirement_ids is not None:
            # Ignore anything that is not an actual requirement id on this project.
            cleaned = sorted(
                {i for i in payload.completed_requirement_ids if i in valid_ids}
            )
            progress.completed_requirement_ids = cleaned

        if payload.submission_url is not None:
            progress.submission_url = payload.submission_url.strip() or None

        if payload.notes is not None:
            progress.notes = payload.notes.strip() or None

        ticked = set(progress.completed_requirement_ids or [])
        all_done = bool(valid_ids) and valid_ids.issubset(ticked)

        newly_completed = all_done and not progress.is_completed
        if newly_completed:
            progress.is_completed = True
            progress.completed_at = datetime.now(timezone.utc)
        elif not all_done:
            # Unticking reopens the project, but XP already awarded is not clawed back.
            progress.is_completed = False
            progress.completed_at = None

        await self.project_repo.add(progress)

        # Building counts as activity, same as finishing a topic.
        if payload.completed_requirement_ids is not None and ticked:
            await self.activity_service.update_daily_activity(user_id)
            await self.streak_repo.update_user_streak(user_id)

        if newly_completed:
            user = await self.user_repo.get_by_id(user_id)
            if user:
                user.total_xp += self.xp_reward(project)
                await self.user_repo.add(user)

        return self._to_read(project, progress)


def get_project_repo(session: AsyncSession = Depends(get_session)) -> ProjectRepository:
    return ProjectRepository(session)


def get_project_user_repo(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(session)


def get_project_streak_repo(session: AsyncSession = Depends(get_session)) -> StreakRepository:
    return StreakRepository(session)


def get_project_service(
    project_repo: ProjectRepository = Depends(get_project_repo),
    user_repo: UserRepository = Depends(get_project_user_repo),
    streak_repo: StreakRepository = Depends(get_project_streak_repo),
    activity_service: ActivityService = Depends(get_activity_service),
) -> ProjectService:
    return ProjectService(project_repo, user_repo, streak_repo, activity_service)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
