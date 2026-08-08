import pytest
from sqlalchemy import select

from app.models.playlist import Playlist
from app.models.progress import UserPlaylist
from app.models.user import User


@pytest.fixture
async def author(session_factory):
    async with session_factory() as session:
        user = User(
            email="author@example.com",
            password_hash="x",
            first_name="Course",
            last_name="Author",
        )
        session.add(user)
        await session.commit()
    return user


@pytest.fixture
async def playlists(session_factory, author):
    """One public React course, one public SQL course, one private course."""
    async with session_factory() as session:
        rows = [
            Playlist(
                title="React.js",
                description="Modern React from components to hooks",
                timeline="",
                objectives=[],
                user_id=author.id,
                slug="react-js",
                is_public=True,
            ),
            Playlist(
                title="SQL & Databases",
                description="Query, model, and optimize relational data",
                timeline="",
                objectives=[],
                user_id=author.id,
                slug="sql-databases",
                is_public=True,
            ),
            Playlist(
                title="Secret Draft",
                description="A private react draft course",
                timeline="",
                objectives=[],
                user_id=author.id,
                slug="secret-draft",
                is_public=False,
            ),
        ]
        session.add_all(rows)
        await session.commit()
    return rows


async def test_gallery_search_matches_title(client, playlists):
    response = await client.get("/api/v1/gallery?q=react")
    assert response.status_code == 200
    slugs = [c["slug"] for c in response.json()]
    assert slugs == ["react-js"]


async def test_gallery_search_matches_description(client, playlists):
    response = await client.get("/api/v1/gallery?q=relational")
    slugs = [c["slug"] for c in response.json()]
    assert slugs == ["sql-databases"]


async def test_gallery_search_never_leaks_private(client, playlists):
    # "react" also appears in the private draft's description
    response = await client.get("/api/v1/gallery?q=react")
    slugs = [c["slug"] for c in response.json()]
    assert "secret-draft" not in slugs


async def test_gallery_short_query_ignored(client, playlists):
    response = await client.get("/api/v1/gallery?q=r")
    assert len(response.json()) == 2  # both public courses, filter ignored


async def test_private_playlist_hidden_from_non_author(client, playlists):
    private = playlists[2]
    response = await client.get(f"/api/v1/playlists/{private.id}")
    assert response.status_code == 404


async def test_private_playlist_visible_to_author(client, auth, author, playlists):
    auth.user = author
    private = playlists[2]
    response = await client.get(f"/api/v1/playlists/{private.id}")
    assert response.status_code == 200


async def test_private_playlist_visible_to_enrolled_user(
    client, test_user, playlists, session_factory
):
    private = playlists[2]
    async with session_factory() as session:
        session.add(UserPlaylist(user_id=test_user.id, playlist_id=private.id))
        await session.commit()
    response = await client.get(f"/api/v1/playlists/{private.id}")
    assert response.status_code == 200


async def test_public_playlist_visible_to_anyone_authed(client, playlists):
    response = await client.get(f"/api/v1/playlists/{playlists[0].id}")
    assert response.status_code == 200


async def test_enrollment_is_not_capped(client, test_user, playlists, session_factory):
    """Library learning is unlimited on every tier , no enrollment quota."""
    for slug in ("react-js", "sql-databases"):
        response = await client.post(f"/api/v1/gallery/{slug}/enroll")
        assert response.status_code == 200

    async with session_factory() as session:
        count = len(
            (
                await session.execute(
                    select(UserPlaylist).where(UserPlaylist.user_id == test_user.id)
                )
            ).scalars().all()
        )
        assert count == 2
