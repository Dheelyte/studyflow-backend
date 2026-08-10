from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import PaymentTransaction, Subscription, UsageCounter


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def month_start_utc() -> date:
    return today_utc().replace(day=1)


class UsageCounterRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID, metric: str, period_start: date) -> UsageCounter | None:
        stmt = select(UsageCounter).where(
            UsageCounter.user_id == user_id,
            UsageCounter.metric == metric,
            UsageCounter.period_start == period_start,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _conditional_increment(
        self, user_id: UUID, metric: str, period_start: date, limit: int
    ) -> bool:
        """Atomic `count += 1 WHERE count < limit`. True iff a unit was taken.

        The predicate lives in the UPDATE so the database re-checks it while
        holding the row lock — correct under READ COMMITTED without an explicit
        SELECT FOR UPDATE. RETURNING tells us whether the row matched.
        """
        stmt = (
            update(UsageCounter)
            .where(
                UsageCounter.user_id == user_id,
                UsageCounter.metric == metric,
                UsageCounter.period_start == period_start,
                UsageCounter.count < limit,
            )
            .values(count=UsageCounter.count + 1)
            .returning(UsageCounter.count)
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def try_consume(
        self, user_id: UUID, metric: str, period_start: date, limit: int
    ) -> bool:
        """Consume one unit if under `limit`. Returns False when at the cap.

        Replaces the old read-modify-write increment, which let N concurrent
        requests at the cap all pass.
        """
        if limit <= 0:
            return False

        if await self._conditional_increment(user_id, metric, period_start, limit):
            return True

        # No row updated: the counter is either at the cap or doesn't exist yet.
        existing = await self.get(user_id, metric, period_start)
        if existing is not None:
            return False  # at the cap

        # First use this period. Insert in a savepoint so a concurrent insert
        # (unique on user+metric+period) rolls back just this attempt, then
        # retry the atomic update once against the row the other request made.
        try:
            async with self.session.begin_nested():
                self.session.add(
                    UsageCounter(
                        user_id=user_id, metric=metric, period_start=period_start, count=1
                    )
                )
                await self.session.flush()
            return True
        except IntegrityError:
            return await self._conditional_increment(user_id, metric, period_start, limit)


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, subscription: Subscription) -> Subscription:
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_by_subscription_code(self, code: str) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.paystack_subscription_code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_for_user(self, user_id: UUID) -> list[Subscription]:
        """Subscriptions still conferring a paid tier (active, winding down, or retrying)."""
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(["active", "non_renewing", "past_due"]),
            )
            .order_by(Subscription.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_user(self, user_id: UUID) -> Subscription | None:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, transaction: PaymentTransaction) -> PaymentTransaction:
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def get_by_reference(self, reference: str) -> PaymentTransaction | None:
        stmt = select(PaymentTransaction).where(PaymentTransaction.reference == reference)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
