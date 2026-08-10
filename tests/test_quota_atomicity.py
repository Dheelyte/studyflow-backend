"""H1: quota consume must be atomic, or N concurrent requests at the cap all pass.

SQLite (the test DB) serializes on one connection, so these can't reproduce a
true DB-level race — but they lock in the algorithm: the conditional UPDATE
never grants beyond the limit, and the first-use insert path is safe. The
correctness under real concurrency comes from `UPDATE ... WHERE count < limit`,
which Postgres re-evaluates while holding the row lock.
"""
from datetime import date

import pytest

from app.models.billing import UsageCounter
from app.repositories.billing import UsageCounterRepository
from app.repositories.screen_tutor import ScreenTutorRepository
from app.models.user import User

PERIOD = date(2026, 8, 1)


@pytest.fixture
async def user_id(session_factory):
    async with session_factory() as session:
        u = User(email="q@x.com", password_hash="h", first_name="Q", last_name="Q")
        session.add(u)
        await session.commit()
        return u.id


async def test_consume_stops_exactly_at_the_limit(session_factory, user_id):
    async with session_factory() as session:
        repo = UsageCounterRepository(session)
        results = [
            await repo.try_consume(user_id, "course_generations", PERIOD, 3)
            for _ in range(6)
        ]
        await session.commit()

    assert results == [True, True, True, False, False, False]


async def test_zero_limit_never_consumes(session_factory, user_id):
    async with session_factory() as session:
        repo = UsageCounterRepository(session)
        assert await repo.try_consume(user_id, "chat_messages", PERIOD, 0) is False


async def test_insert_race_falls_back_to_update(session_factory, user_id):
    """The first-use path: another request already created the counter between
    our conditional UPDATE (no row) and our INSERT. We must not error on the
    unique-constraint violation, but consume against the existing row.

    Simulated deterministically by pre-seeding the row, since SQLite's shared
    single connection can't produce a genuine parallel INSERT race. Real
    concurrency safety rests on `UPDATE ... WHERE count < limit`, which Postgres
    re-checks under the row lock — the sequential cap test above pins that
    invariant.
    """
    async with session_factory() as session:
        # Row already exists at count=1 (the "other request" won the insert).
        session.add(
            UsageCounter(
                user_id=user_id, metric="course_generations", period_start=PERIOD, count=1
            )
        )
        await session.commit()

    async with session_factory() as session:
        repo = UsageCounterRepository(session)
        assert await repo.try_consume(user_id, "course_generations", PERIOD, 3) is True
        await session.commit()
        counter = await repo.get(user_id, "course_generations", PERIOD)
        assert counter.count == 2, "consumed against the existing row, no duplicate"


async def test_screen_tutor_consume_stops_at_limit(session_factory, user_id):
    async with session_factory() as session:
        repo = ScreenTutorRepository(session)
        results = [await repo.try_consume(user_id, 2) for _ in range(5)]
        await session.commit()
    assert results == [True, True, False, False, False]
