from fastapi import APIRouter, Depends, Query

from ..db.session import db_session
from ..dependencies.auth import AuthUserDep
from ..dependencies.playlist import PlaylistIdDep
from ..schema.gallery import (
    EnrollResponse,
    GalleryCourseCard,
    GalleryCourseDetail,
    PublishRequest,
    PublishResponse,
)
from ..services.gallery import GalleryServiceDep


# Public browsing — unauthenticated so gallery pages are server-renderable and indexable.
public_router = APIRouter(tags=["Gallery"], dependencies=[Depends(db_session)])


@public_router.get("/gallery", response_model=list[GalleryCourseCard])
async def list_public_courses(
    service: GalleryServiceDep,
    limit: int = Query(default=24, ge=1, le=60),
    offset: int = Query(default=0, ge=0),
    featured: bool = Query(default=False),
):
    return await service.list_public_courses(
        limit=limit, offset=offset, featured_only=featured
    )


@public_router.get("/gallery-slugs")
async def list_public_course_slugs(service: GalleryServiceDep):
    """Slug + publish date for every public course, used to build the sitemap."""
    rows = await service.list_public_slugs()
    return [
        {"slug": slug, "published_at": published_at}
        for slug, published_at in rows
    ]


@public_router.get("/gallery/{slug}", response_model=GalleryCourseDetail)
async def get_public_course(slug: str, service: GalleryServiceDep):
    return await service.get_public_course(slug)


# Authenticated actions
router = APIRouter(tags=["Gallery"], dependencies=[Depends(db_session)])


@router.post("/playlists/{playlist_ref}/publish", response_model=PublishResponse)
async def set_playlist_publish_state(
    playlist_id: PlaylistIdDep,
    payload: PublishRequest,
    auth_user: AuthUserDep,
    service: GalleryServiceDep,
):
    return await service.set_publish_state(
        playlist_id, auth_user.id, payload.is_public
    )


@router.post("/gallery/{slug}/enroll", response_model=EnrollResponse)
async def enroll_in_public_course(
    slug: str,
    auth_user: AuthUserDep,
    service: GalleryServiceDep,
):
    return await service.enroll(slug, auth_user.id)
