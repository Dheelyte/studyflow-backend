from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.session import get_session
from ..exceptions.base import QuotaExceededError
from ..models.user import User
from ..repositories.billing import UsageCounterRepository, month_start_utc, today_utc
from ..repositories.screen_tutor import ScreenTutorRepository

# Metric names are stable identifiers , they appear in usage_counters rows and
# in 402 bodies the frontend switches on.
METRIC_COURSE_GENERATIONS = "course_generations"
METRIC_CHAT_MESSAGES = "chat_messages"
METRIC_SCREEN_TUTOR = "screen_tutor_questions"

# Which period a metric counts over.
_MONTHLY_METRICS = {METRIC_COURSE_GENERATIONS}


@dataclass(frozen=True)
class PlanLimits:
    course_generations_monthly: int
    chat_messages_daily: int
    screen_tutor_daily: int


def get_limits(plan: str) -> PlanLimits:
    if plan == "max":
        return PlanLimits(
            course_generations_monthly=settings.MAX_COURSE_GENERATIONS_MONTHLY,
            chat_messages_daily=settings.MAX_CHAT_MESSAGES_DAILY,
            screen_tutor_daily=settings.MAX_SCREEN_TUTOR_DAILY,
        )
    if plan == "pro":
        return PlanLimits(
            course_generations_monthly=settings.PRO_COURSE_GENERATIONS_MONTHLY,
            chat_messages_daily=settings.PRO_CHAT_MESSAGES_DAILY,
            screen_tutor_daily=settings.PRO_SCREEN_TUTOR_DAILY,
        )
    return PlanLimits(
        course_generations_monthly=settings.FREE_COURSE_GENERATIONS_MONTHLY,
        chat_messages_daily=settings.FREE_CHAT_MESSAGES_DAILY,
        screen_tutor_daily=settings.FREE_SCREEN_TUTOR_DAILY,
    )


def _limit_for(plan: str, metric: str) -> int:
    limits = get_limits(plan)
    if metric == METRIC_COURSE_GENERATIONS:
        return limits.course_generations_monthly
    if metric == METRIC_CHAT_MESSAGES:
        return limits.chat_messages_daily
    if metric == METRIC_SCREEN_TUTOR:
        return limits.screen_tutor_daily
    raise ValueError(f"Unknown metric: {metric}")


def _period_start(metric: str) -> date:
    return month_start_utc() if metric in _MONTHLY_METRICS else today_utc()


class EntitlementsService:
    def __init__(self, usage_repo: UsageCounterRepository, screen_tutor_repo: ScreenTutorRepository):
        self.usage_repo = usage_repo
        self.screen_tutor_repo = screen_tutor_repo

    async def get_used(self, user: User, metric: str) -> int:
        # Screen tutor predates the generic counter and keeps its own table.
        if metric == METRIC_SCREEN_TUTOR:
            usage = await self.screen_tutor_repo.get_usage(user.id)
            return usage.question_count if usage else 0
        counter = await self.usage_repo.get(user.id, metric, _period_start(metric))
        return counter.count if counter else 0

    async def ensure_can(self, user: User, metric: str) -> None:
        """Read-only pre-check, for streaming routes that must 402 before the stream opens."""
        limit = _limit_for(user.plan, metric)
        used = await self.get_used(user, metric)
        if used >= limit:
            raise QuotaExceededError(metric=metric, limit=limit, used=used, plan=user.plan)

    async def check_and_increment(self, user: User, metric: str) -> int:
        """Charge-before-generate: raise 402 at the cap, else consume one unit.

        The check and the consume are a single atomic step, so N concurrent
        requests at the cap can't all slip through. Returns units remaining.
        """
        limit = _limit_for(user.plan, metric)
        if metric == METRIC_SCREEN_TUTOR:
            consumed = await self.screen_tutor_repo.try_consume(user.id, limit)
        else:
            consumed = await self.usage_repo.try_consume(
                user.id, metric, _period_start(metric), limit
            )
        if not consumed:
            used = await self.get_used(user, metric)
            raise QuotaExceededError(metric=metric, limit=limit, used=used, plan=user.plan)
        return max(0, limit - await self.get_used(user, metric))

    async def get_usage_summary(self, user: User) -> dict:
        limits = get_limits(user.plan)
        return {
            "course_generations": {
                "used": await self.get_used(user, METRIC_COURSE_GENERATIONS),
                "limit": limits.course_generations_monthly,
                "period": "monthly",
            },
            "chat_messages": {
                "used": await self.get_used(user, METRIC_CHAT_MESSAGES),
                "limit": limits.chat_messages_daily,
                "period": "daily",
            },
            "screen_tutor_questions": {
                "used": await self.get_used(user, METRIC_SCREEN_TUTOR),
                "limit": limits.screen_tutor_daily,
                "period": "daily",
            },
        }


def get_entitlements_service(
    session: AsyncSession = Depends(get_session),
) -> EntitlementsService:
    return EntitlementsService(UsageCounterRepository(session), ScreenTutorRepository(session))


EntitlementsServiceDep = Annotated[EntitlementsService, Depends(get_entitlements_service)]
