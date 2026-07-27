from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..exceptions.base import ForbiddenError, NotFoundError
from ..models.progress import UserPlaylist
from ..repositories.playlist import PlaylistRepository
from ..repositories.project import ProjectRepository
from ..schema.gallery import (
    EnrollResponse,
    GalleryCourseCard,
    GalleryCourseDetail,
    GalleryLessonOutline,
    GalleryModuleOutline,
    GalleryTopicOutline,
    PublishResponse,
)
from ..schema.project import ProjectSummary
from ..utils.slug import generate_unique_slug


class GalleryService:
    def __init__(self, playlist_repo: PlaylistRepository):
        self.playlist_repo = playlist_repo

    @staticmethod
    def _author_name(playlist) -> str | None:
        """First name plus last initial — publishing a course shouldn't publish a full name."""
        author = getattr(playlist, 'author', None)
        if not author:
            return None
        first = (author.first_name or '').strip()
        last = (author.last_name or '').strip()
        if first and last:
            return f"{first} {last[0]}."
        return first or None

    @staticmethod
    def _level(playlist) -> str | None:
        level = playlist.level
        return getattr(level, 'value', level)

    def _to_card(self, row) -> GalleryCourseCard:
        playlist = row[0]
        return GalleryCourseCard(
            id=playlist.id,
            slug=playlist.slug,
            title=playlist.title,
            description=playlist.description,
            level=self._level(playlist),
            module_count=row.module_count,
            lesson_count=row.lesson_count,
            topic_count=row.topic_count,
            learner_count=row.learner_count,
            author_name=self._author_name(playlist),
            is_featured=playlist.is_featured,
            published_at=playlist.published_at,
        )

    async def list_public_courses(
        self,
        limit: int = 24,
        offset: int = 0,
        featured_only: bool = False,
    ) -> list[GalleryCourseCard]:
        rows = await self.playlist_repo.get_public_playlists(
            limit=limit, offset=offset, featured_only=featured_only
        )
        return [self._to_card(row) for row in rows]

    async def get_public_course(self, slug: str) -> GalleryCourseDetail:
        playlist = await self.playlist_repo.get_public_playlist_by_slug(slug)
        if not playlist:
            raise NotFoundError("Course not found")

        (
            module_count,
            lesson_count,
            topic_count,
            learner_count,
        ) = await self.playlist_repo.get_playlist_counts(playlist.id)

        modules = []
        for module in sorted(playlist.modules, key=lambda m: m.order):
            lessons = []
            for lesson in sorted(module.lessons, key=lambda l: l.order):
                topics = [
                    GalleryTopicOutline(title=topic.title, description=topic.description)
                    for topic in sorted(lesson.topics, key=lambda t: t.order)
                ]
                lessons.append(
                    GalleryLessonOutline(
                        title=lesson.title,
                        estimated_time=lesson.estimated_time,
                        topics=topics,
                    )
                )
            modules.append(
                GalleryModuleOutline(
                    title=module.title,
                    description=module.description,
                    order=module.order,
                    lessons=lessons,
                )
            )

        return GalleryCourseDetail(
            id=playlist.id,
            slug=playlist.slug,
            title=playlist.title,
            description=playlist.description,
            level=self._level(playlist),
            module_count=module_count,
            lesson_count=lesson_count,
            topic_count=topic_count,
            learner_count=learner_count,
            author_name=self._author_name(playlist),
            is_featured=playlist.is_featured,
            published_at=playlist.published_at,
            objectives=playlist.objectives or [],
            modules=modules,
            capstone=await self._capstone_summary(playlist.id),
        )

    async def _capstone_summary(self, playlist_id: int) -> ProjectSummary | None:
        """Only surfaces a capstone that already exists — never generates one for a
        public request, which would put an LLM call behind an unauthenticated endpoint."""
        project = await ProjectRepository(self.playlist_repo.session).get_capstone(playlist_id)
        if not project:
            return None
        return ProjectSummary(
            title=project.title,
            summary=project.summary,
            estimated_time=project.estimated_time,
        )

    async def set_publish_state(
        self, playlist_id: int, user_id: UUID, is_public: bool
    ) -> PublishResponse:
        playlist = await self.playlist_repo.get_playlist_by_id(playlist_id)
        if not playlist:
            raise NotFoundError("Playlist not found")
        if playlist.user_id != user_id:
            raise ForbiddenError("You can only publish courses you created")

        if is_public:
            # Slug is kept on unpublish so re-publishing restores the same public URL.
            if not playlist.slug:
                playlist.slug = await generate_unique_slug(self.playlist_repo, playlist.title)
            if not playlist.published_at:
                playlist.published_at = datetime.now(timezone.utc)

        playlist.is_public = is_public
        await self.playlist_repo.add(playlist)

        return PublishResponse(
            id=playlist.id,
            is_public=playlist.is_public,
            slug=playlist.slug,
            published_at=playlist.published_at,
        )

    async def enroll(self, slug: str, user_id: UUID) -> EnrollResponse:
        """Enrol in a published course. Progress is per-user, so the course is shared, not copied."""
        playlist_id = await self.playlist_repo.get_public_playlist_id_by_slug(slug)
        if not playlist_id:
            raise NotFoundError("Course not found")

        existing = await self.playlist_repo.get_user_playlist(playlist_id, user_id)
        if existing:
            return EnrollResponse(playlist_id=playlist_id, slug=slug, already_enrolled=True)

        await self.playlist_repo.add(
            UserPlaylist(user_id=user_id, playlist_id=playlist_id)
        )
        return EnrollResponse(playlist_id=playlist_id, slug=slug, already_enrolled=False)

    async def list_public_slugs(self, limit: int = 1000):
        return await self.playlist_repo.get_public_slugs(limit=limit)


def get_gallery_repo(session: AsyncSession = Depends(get_session)) -> PlaylistRepository:
    return PlaylistRepository(session)


def get_gallery_service(
    playlist_repo: PlaylistRepository = Depends(get_gallery_repo),
) -> GalleryService:
    return GalleryService(playlist_repo)


GalleryServiceDep = Annotated[GalleryService, Depends(get_gallery_service)]
