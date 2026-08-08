from datetime import date

from sqlalchemy import select

from app.config import settings
from app.models.billing import UsageCounter
from app.repositories.billing import month_start_utc, today_utc

GENERATE_PATH = "/api/v1/generate-curriculum?topic=React"
STREAM_PATH = "/api/v1/topics/1/chat/messages/stream"


async def seed_counter(session_factory, user, metric, period_start, count):
    async with session_factory() as session:
        session.add(
            UsageCounter(
                user_id=user.id, metric=metric, period_start=period_start, count=count
            )
        )
        await session.commit()


async def test_generation_needs_auth(client, auth):
    auth.user = None
    response = await client.get(GENERATE_PATH)
    assert response.status_code == 401


async def test_generation_quota_402_shape(client, test_user, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "FREE_COURSE_GENERATIONS_MONTHLY", 1)

    first = await client.get(GENERATE_PATH)
    assert first.status_code == 200

    second = await client.get(GENERATE_PATH)
    assert second.status_code == 402
    body = second.json()
    assert body == {
        "detail": body["detail"],
        "code": "quota_exceeded",
        "metric": "course_generations",
        "limit": 1,
        "used": 1,
        "plan": "free",
    }
    assert "limit" in body["detail"] or body["detail"]


async def test_generation_charged_before_generate(client, test_user, session_factory):
    await client.get(GENERATE_PATH)
    async with session_factory() as session:
        counter = (
            await session.execute(
                select(UsageCounter).where(
                    UsageCounter.user_id == test_user.id,
                    UsageCounter.metric == "course_generations",
                )
            )
        ).scalar_one()
        assert counter.count == 1
        assert counter.period_start == month_start_utc()


async def test_pro_user_passes_free_limit(client, auth, test_user, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "FREE_COURSE_GENERATIONS_MONTHLY", 1)
    await seed_counter(
        session_factory, test_user, "course_generations", month_start_utc(), 1
    )
    auth.user.plan = "pro"

    response = await client.get(GENERATE_PATH)
    assert response.status_code == 200


async def test_counter_resets_across_period(client, test_user, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "FREE_COURSE_GENERATIONS_MONTHLY", 1)
    # Last month's counter is at the limit , this month starts fresh.
    await seed_counter(
        session_factory, test_user, "course_generations", date(2026, 7, 1), 1
    )
    response = await client.get(GENERATE_PATH)
    assert response.status_code == 200


async def test_chat_stream_precheck_returns_clean_402(client, test_user, session_factory):
    await seed_counter(
        session_factory,
        test_user,
        "chat_messages",
        today_utc(),
        settings.FREE_CHAT_MESSAGES_DAILY,
    )
    response = await client.post(STREAM_PATH, json={"content": "hi"})
    assert response.status_code == 402
    body = response.json()
    assert body["code"] == "quota_exceeded"
    assert body["metric"] == "chat_messages"


async def test_billing_status_reports_usage(client, test_user, session_factory):
    await seed_counter(
        session_factory, test_user, "course_generations", month_start_utc(), 2
    )
    response = await client.get("/api/v1/billing/status")
    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["usage"]["course_generations"]["used"] == 2
    assert body["usage"]["course_generations"]["limit"] == settings.FREE_COURSE_GENERATIONS_MONTHLY
    assert body["limits"]["chat_messages_daily"] == settings.FREE_CHAT_MESSAGES_DAILY
    assert body["subscription"] is None
