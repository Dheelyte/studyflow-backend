from datetime import date, datetime

from sqlalchemy import (
    JSON,
    UUID,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Subscription(Base):
    """Paystack subscription bookkeeping for a paid tier.

    user.plan is the fast-read entitlement flag; this table records how the
    user got it. Only webhook handling and the verify fallback write here.
    """

    __tablename__ = "subscriptions"

    user_id = mapped_column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # pro | max
    # active | non_renewing | past_due | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    interval: Mapped[str] = mapped_column(String(20), nullable=False)  # monthly | annual

    paystack_plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
    paystack_customer_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paystack_subscription_code: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    paystack_email_token: Mapped[str | None] = mapped_column(String(64), nullable=True)

    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<Subscription user={self.user_id} tier={self.tier} status={self.status}>"


class UsageCounter(Base):
    """Generic per-user, per-period usage counter , one row per (user, metric, period).

    Generalizes the ScreenTutorUsage pattern: period_start is the UTC day for
    daily metrics and the first of the UTC month for monthly ones.
    """

    __tablename__ = "usage_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id = mapped_column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "metric", "period_start", name="unique_user_metric_period"),
    )


class PaymentTransaction(Base):
    """One row per Paystack charge; the unique reference is the webhook idempotency key."""

    __tablename__ = "payment_transactions"

    user_id = mapped_column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="NGN")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_event: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<PaymentTransaction {self.reference} {self.status}>"
