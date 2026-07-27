from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..exceptions.base import NotFoundError
from ..repositories.playlist import PlaylistRepository


async def resolve_playlist_ref(
    playlist_ref: str,
    session: AsyncSession = Depends(get_session),
) -> int:
    """Turn a `{playlist_ref}` path segment into a playlist id.

    Accepts a slug (the canonical form) or a numeric id, so links and bookmarks
    created before slugs existed keep working.
    """
    repo = PlaylistRepository(session)
    playlist_id = await repo.resolve_playlist_id(playlist_ref)
    if playlist_id is None:
        raise NotFoundError("Course not found")
    return playlist_id


PlaylistIdDep = Annotated[int, Depends(resolve_playlist_ref)]
