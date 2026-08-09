import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.session import get_session
from ..exceptions.base import BadRequestError, NotFoundError
from ..models.billing import PaymentTransaction, Subscription
from ..models.user import User
from ..repositories.billing import PaymentRepository, SubscriptionRepository
from ..repositories.user import UserRepository
from ..schema.billing import (
    BillingStatus,
    CheckoutResponse,
    PlanLimitsRead,
    ReconcileReport,
    SubscriptionRead,
    UsageRead,
    VerifyResponse,
)
from ..services.entitlements import EntitlementsService, get_entitlements_service, get_limits
from ..services.paystack import PaystackClient, PaystackError

logger = logging.getLogger(__name__)

PAID_TIERS = ("pro", "max")
INTERVALS = ("monthly", "annual")


def _extract_plan_code(data: dict) -> str:
    """Pull the plan code out of a Paystack payload, whatever shape it arrived in.

    Paystack is not consistent about this field: `transaction/verify` returns
    `plan` as a bare plan-code string (or "" for a one-off charge), while the
    `charge.success` and `subscription.create` webhooks nest it as an object
    under `plan.plan_code`. Some payloads carry a top-level `plan_code` instead.
    Assuming any single shape crashes on the others.
    """
    plan = data.get("plan")
    code = ""
    if isinstance(plan, str):
        code = plan
    elif isinstance(plan, dict):
        code = plan.get("plan_code") or ""

    if not code:
        top_level = data.get("plan_code")
        if isinstance(top_level, str):
            code = top_level

    return code.strip()


def _nested(data: dict, key: str, field: str) -> str | None:
    """Read data[key][field] without assuming data[key] is a dict.

    Same defensive reason as _extract_plan_code: Paystack sometimes sends a
    bare identifier string where a nested object is documented, and an
    AttributeError inside a webhook 500s the endpoint, which Paystack retries
    and can eventually disable.
    """
    value = data.get(key)
    if isinstance(value, dict):
        return value.get(field)
    return None


def _as_utc(value: datetime | None) -> datetime | None:
    """Treat a stored naive datetime as UTC.

    Postgres timestamptz round-trips tz-aware, but SQLite (tests) and some
    drivers hand back naive values, and comparing the two raises TypeError.
    Everything we store here is UTC, so attaching it is safe.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _parse_paystack_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class BillingService:
    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        payment_repo: PaymentRepository,
        user_repo: UserRepository,
        entitlements: EntitlementsService,
        paystack: PaystackClient,
    ):
        self.subscription_repo = subscription_repo
        self.payment_repo = payment_repo
        self.user_repo = user_repo
        self.entitlements = entitlements
        self.paystack = paystack

    # --- Plan code mapping -------------------------------------------------

    @staticmethod
    def plan_code_for(tier: str, interval: str) -> str:
        codes = {
            ("pro", "monthly"): settings.PAYSTACK_PLAN_CODE_PRO_MONTHLY,
            ("pro", "annual"): settings.PAYSTACK_PLAN_CODE_PRO_ANNUAL,
            ("max", "monthly"): settings.PAYSTACK_PLAN_CODE_MAX_MONTHLY,
            ("max", "annual"): settings.PAYSTACK_PLAN_CODE_MAX_ANNUAL,
        }
        code = codes.get((tier, interval), "")
        if not code:
            raise BadRequestError(f"No Paystack plan configured for {tier}/{interval}")
        return code

    @staticmethod
    def tier_for_plan_code(plan_code: str) -> tuple[str, str] | None:
        """(tier, interval) for a Paystack plan code, or None if it isn't ours."""
        mapping = {
            settings.PAYSTACK_PLAN_CODE_PRO_MONTHLY: ("pro", "monthly"),
            settings.PAYSTACK_PLAN_CODE_PRO_ANNUAL: ("pro", "annual"),
            settings.PAYSTACK_PLAN_CODE_MAX_MONTHLY: ("max", "monthly"),
            settings.PAYSTACK_PLAN_CODE_MAX_ANNUAL: ("max", "annual"),
        }
        mapping.pop("", None)
        return mapping.get(plan_code)

    # --- Checkout / verify -------------------------------------------------

    async def checkout(self, user: User, tier: str, interval: str) -> CheckoutResponse:
        if not settings.BILLING_ENABLED:
            raise BadRequestError("Billing is not available yet")
        if tier not in PAID_TIERS or interval not in INTERVALS:
            raise BadRequestError("Unknown plan")

        # Tier switch: Paystack can't swap a subscription's plan in place, so
        # wind down the old subscription and start a new checkout.
        for sub in await self.subscription_repo.get_active_for_user(user.id):
            if sub.tier != tier or sub.interval != interval:
                await self._disable_subscription(sub)

        plan_code = self.plan_code_for(tier, interval)

        # Look the plan up rather than hardcoding prices: Paystack requires an
        # amount on initialize even though the plan overrides it, and this also
        # catches a plan code that doesn't exist in the current mode — the
        # classic "test plan codes still configured in live" mistake, which
        # would otherwise only surface after a customer had been charged.
        try:
            plan = await self.paystack.fetch_plan(plan_code)
        except PaystackError as e:
            logger.error("Paystack plan %s could not be fetched: %s", plan_code, e)
            raise BadRequestError(
                "This plan isn't available right now. Please try again later."
            )

        amount_kobo = plan.get("amount") or 0
        if not amount_kobo:
            logger.error("Paystack plan %s returned no amount", plan_code)
            raise BadRequestError(
                "This plan isn't available right now. Please try again later."
            )

        data = await self.paystack.initialize_transaction(
            email=user.email,
            plan_code=plan_code,
            amount_kobo=amount_kobo,
            callback_url=f"{settings.FRONTEND_URL}/billing/callback",
            metadata={"user_id": str(user.id)},
        )
        return CheckoutResponse(
            authorization_url=data["authorization_url"], reference=data["reference"]
        )

    async def verify(self, user: User, reference: str) -> VerifyResponse:
        """Callback-page fallback: activate directly off a verified transaction
        in case the webhook hasn't landed yet. Idempotent via unique reference."""
        try:
            data = await self.paystack.verify_transaction(reference)
        except PaystackError:
            raise NotFoundError("Transaction not found")

        if data.get("status") != "success":
            return VerifyResponse(status=data.get("status", "pending"), plan=user.plan)

        plan_code = _extract_plan_code(data)
        resolved = self.tier_for_plan_code(plan_code)
        if not resolved:
            logger.warning("Verified transaction %s has unknown plan code %r", reference, plan_code)
            return VerifyResponse(status="pending", plan=user.plan)
        tier, interval = resolved

        await self._record_transaction(user, reference, data)
        await self._activate(user, tier, interval, plan_code, data)
        return VerifyResponse(status="success", plan=user.plan)

    # --- Webhook -----------------------------------------------------------

    async def handle_webhook(self, event: dict) -> None:
        event_type = event.get("event", "")
        data = event.get("data", {}) or {}

        if event_type == "charge.success":
            await self._on_charge_success(data)
        elif event_type == "subscription.create":
            await self._on_subscription_create(data)
        elif event_type == "subscription.not_renew":
            await self._on_subscription_status(data, "non_renewing")
        elif event_type in ("invoice.create", "invoice.update"):
            # Renewal cycle. charge.success keeps the tier alive, but only these
            # carry the *new* next_payment_date, so without them the stored
            # renewal date freezes at whatever the first payment set.
            await self._on_invoice(data)
        elif event_type == "invoice.payment_failed":
            await self._on_invoice_failed(data)
        elif event_type == "subscription.disable":
            await self._on_subscription_disable(data)
        else:
            logger.info("Ignoring Paystack event %s", event_type)

    async def _resolve_user(self, data: dict) -> User | None:
        metadata = data.get("metadata") or {}
        user_id = metadata.get("user_id")
        if user_id:
            try:
                user = await self.user_repo.get_by_id(UUID(str(user_id)))
            except ValueError:
                user = None
            if user:
                return user
        email = _nested(data, "customer", "email")
        if email:
            return await self.user_repo.get_by_email(email)
        return None

    async def _on_charge_success(self, data: dict) -> None:
        plan_code = _extract_plan_code(data)
        resolved = self.tier_for_plan_code(plan_code)
        if not resolved:
            # A charge unrelated to our subscription plans (or plan codes not configured).
            logger.info("charge.success with unknown plan code %r ignored", plan_code)
            return
        user = await self._resolve_user(data)
        if not user:
            logger.error("charge.success: could not resolve user (ref=%s)", data.get("reference"))
            return

        reference = data.get("reference", "")
        if reference and await self.payment_repo.get_by_reference(reference):
            return  # replayed webhook
        await self._record_transaction(user, reference, data)

        tier, interval = resolved
        await self._activate(user, tier, interval, plan_code, data)

    async def _on_subscription_create(self, data: dict) -> None:
        user = await self._resolve_user(data)
        if not user:
            logger.error("subscription.create: could not resolve user")
            return
        plan_code = _extract_plan_code(data)
        resolved = self.tier_for_plan_code(plan_code)
        if not resolved:
            return
        tier, interval = resolved

        code = data.get("subscription_code")
        subscription = await self.subscription_repo.get_by_subscription_code(code) if code else None
        if not subscription:
            subscription = await self._get_or_create_subscription(user, tier, interval, plan_code)
        subscription.paystack_subscription_code = code
        subscription.paystack_email_token = data.get("email_token")
        subscription.paystack_customer_code = _nested(data, "customer", "customer_code")
        subscription.status = "active"
        subscription.current_period_end = _parse_paystack_datetime(data.get("next_payment_date"))
        await self.subscription_repo.add(subscription)

        user.plan = tier
        user.plan_expires_at = subscription.current_period_end
        await self.user_repo.add(user)

    async def _on_subscription_status(self, data: dict, status: str) -> None:
        code = data.get("subscription_code")
        if not code:
            return
        subscription = await self.subscription_repo.get_by_subscription_code(code)
        if subscription:
            subscription.status = status
            await self.subscription_repo.add(subscription)

    async def _on_invoice(self, data: dict) -> None:
        """Roll the stored renewal date forward on each billing cycle."""
        code = _nested(data, "subscription", "subscription_code")
        if not code:
            return
        subscription = await self.subscription_repo.get_by_subscription_code(code)
        if not subscription:
            return

        next_payment = _parse_paystack_datetime(
            _nested(data, "subscription", "next_payment_date")
        )
        if next_payment:
            subscription.current_period_end = next_payment
            # Keep the denormalised copy on the user in step, or the lazy expiry
            # check would still see the previous cycle's date.
            user = await self.user_repo.get_by_id(subscription.user_id)
            if user and user.plan != "free":
                user.plan_expires_at = next_payment
                await self.user_repo.add(user)

        # A paid invoice clears a previous past_due state. Never resurrect a
        # cancelled or non-renewing subscription — those are winding down on
        # purpose and must still end at period close.
        paid = data.get("status") == "success" or data.get("paid") is True
        if paid and subscription.status == "past_due":
            subscription.status = "active"

        await self.subscription_repo.add(subscription)

    async def _on_invoice_failed(self, data: dict) -> None:
        code = _nested(data, "subscription", "subscription_code")
        if not code:
            return
        subscription = await self.subscription_repo.get_by_subscription_code(code)
        if subscription:
            subscription.status = "past_due"
            await self.subscription_repo.add(subscription)

    async def _on_subscription_disable(self, data: dict) -> None:
        """Fires at period end after a cancel (or final payment failure) , the
        single place a user is downgraded to free."""
        code = data.get("subscription_code")
        subscription = await self.subscription_repo.get_by_subscription_code(code) if code else None
        if not subscription:
            return
        subscription.status = "cancelled"
        await self.subscription_repo.add(subscription)

        user = await self.user_repo.get_by_id(subscription.user_id)
        if not user:
            return
        # A tier switch disables the old subscription while a new one is live ,
        # only downgrade when nothing else still confers a paid tier.
        remaining = [
            s for s in await self.subscription_repo.get_active_for_user(user.id)
            if s.id != subscription.id
        ]
        if remaining:
            user.plan = remaining[0].tier
            user.plan_expires_at = remaining[0].current_period_end
        else:
            user.plan = "free"
            user.plan_expires_at = None
        await self.user_repo.add(user)

    # --- Cancel / status ---------------------------------------------------

    async def cancel(self, user: User) -> SubscriptionRead:
        subs = await self.subscription_repo.get_active_for_user(user.id)
        if not subs:
            raise NotFoundError("No active subscription to cancel")
        subscription = subs[0]
        await self._disable_subscription(subscription)
        return SubscriptionRead.model_validate(subscription)

    async def reconcile_plan(self, user: User) -> None:
        """Safety net for a missed `subscription.disable` webhook.

        `user.plan` is the only gate on paid features, and that webhook is
        normally the only thing that clears it — so if Paystack never delivers
        it, the user keeps a paid tier forever. Called lazily when someone uses
        a feature their subscription pays for.

        Deliberately fails open: a Paystack outage must never revoke a paying
        customer's access.
        """
        if user.plan == "free" or not user.plan_expires_at:
            return

        deadline = _as_utc(user.plan_expires_at) + timedelta(
            days=settings.PLAN_EXPIRY_GRACE_DAYS
        )
        if datetime.now(timezone.utc) <= deadline:
            return

        subscriptions = await self.subscription_repo.get_active_for_user(user.id)
        if not subscriptions:
            # Paid tier with nothing backing it.
            await self._downgrade(user, None)
            return

        subscription = subscriptions[0]
        code = subscription.paystack_subscription_code
        if not code:
            await self._downgrade(user, subscription)
            return

        try:
            remote = await self.paystack.fetch_subscription(code)
        except PaystackError as e:
            logger.error("Could not reconcile subscription %s: %s", code, e)
            return  # fail open

        next_payment = _parse_paystack_datetime(remote.get("next_payment_date"))
        still_live = remote.get("status") in ("active", "attention")

        if still_live and next_payment and next_payment > datetime.now(timezone.utc):
            # The disable webhook was simply missed, or a renewal landed without
            # us hearing about it. Heal the dates so this stops re-checking.
            subscription.current_period_end = next_payment
            subscription.status = "active"
            await self.subscription_repo.add(subscription)
            user.plan_expires_at = next_payment
            await self.user_repo.add(user)
            logger.info("Reconciled subscription %s: still active", code)
            return

        logger.info("Reconciled subscription %s: expired, downgrading", code)
        await self._downgrade(user, subscription)

    async def sweep_expired_plans(self, limit: int | None = None) -> ReconcileReport:
        """Reconcile lapsed subscribers who never came back.

        The lazy check only fires when someone uses a paid feature, so a user
        who lapses and stops visiting keeps a paid tier in the database forever.
        That costs nothing real but inflates subscriber counts, so a scheduled
        sweep settles them.
        """
        limit = limit or settings.RECONCILE_BATCH_LIMIT
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.PLAN_EXPIRY_GRACE_DAYS
        )
        users = await self.user_repo.get_expired_paid_users(cutoff, limit)

        report = ReconcileReport(scanned=len(users))
        for user in users:
            before = user.plan
            try:
                await self.reconcile_plan(user)
            except Exception:
                # One unhealthy account must not abort the batch; the next run
                # retries it. reconcile_plan already swallows PaystackError, so
                # reaching here means something unexpected.
                logger.exception("Sweep failed for user %s", user.id)
                report.errors += 1
                continue

            if user.plan == "free" and before != "free":
                report.downgraded += 1
            elif user.plan_expires_at and _as_utc(user.plan_expires_at) > cutoff:
                report.still_active += 1
            else:
                report.unchanged += 1

        logger.info(
            "Reconcile sweep: scanned=%d downgraded=%d still_active=%d unchanged=%d errors=%d",
            report.scanned, report.downgraded, report.still_active,
            report.unchanged, report.errors,
        )
        return report

    async def _downgrade(self, user: User, subscription: Subscription | None) -> None:
        if subscription is not None:
            subscription.status = "cancelled"
            await self.subscription_repo.add(subscription)
        user.plan = "free"
        user.plan_expires_at = None
        await self.user_repo.add(user)

    async def status(self, user: User) -> BillingStatus:
        limits = get_limits(user.plan)
        usage = await self.entitlements.get_usage_summary(user)
        subscription = None
        subs = await self.subscription_repo.get_active_for_user(user.id)
        if subs:
            subscription = SubscriptionRead.model_validate(subs[0])
        return BillingStatus(
            plan=user.plan,
            limits=PlanLimitsRead(
                course_generations_monthly=limits.course_generations_monthly,
                chat_messages_daily=limits.chat_messages_daily,
                screen_tutor_daily=limits.screen_tutor_daily,
            ),
            usage=UsageRead(**usage),
            subscription=subscription,
        )

    # --- Internals ---------------------------------------------------------

    async def _disable_subscription(self, subscription: Subscription) -> None:
        code = subscription.paystack_subscription_code
        token = subscription.paystack_email_token
        if code and not token:
            try:
                token = (await self.paystack.fetch_subscription(code)).get("email_token")
                subscription.paystack_email_token = token
            except PaystackError:
                pass
        if code and token:
            try:
                await self.paystack.disable_subscription(code, token)
            except PaystackError as e:
                logger.error("Failed to disable subscription %s: %s", code, e)
        subscription.status = "non_renewing"
        await self.subscription_repo.add(subscription)

    async def _get_or_create_subscription(
        self, user: User, tier: str, interval: str, plan_code: str
    ) -> Subscription:
        for sub in await self.subscription_repo.get_active_for_user(user.id):
            if sub.tier == tier and sub.interval == interval:
                return sub
        return await self.subscription_repo.add(
            Subscription(
                user_id=user.id,
                tier=tier,
                interval=interval,
                status="active",
                paystack_plan_code=plan_code,
            )
        )

    async def _record_transaction(self, user: User, reference: str, data: dict) -> None:
        if not reference or await self.payment_repo.get_by_reference(reference):
            return
        await self.payment_repo.add(
            PaymentTransaction(
                user_id=user.id,
                reference=reference,
                amount_kobo=data.get("amount") or 0,
                currency=data.get("currency") or "NGN",
                status=data.get("status", "success"),
                paid_at=_parse_paystack_datetime(data.get("paid_at") or data.get("paidAt")),
                raw_event={"channel": data.get("channel"), "plan": data.get("plan")},
            )
        )

    async def _activate(
        self, user: User, tier: str, interval: str, plan_code: str, data: dict
    ) -> None:
        subscription = await self._get_or_create_subscription(user, tier, interval, plan_code)
        subscription.status = "active"
        customer_code = _nested(data, "customer", "customer_code")
        if customer_code:
            subscription.paystack_customer_code = customer_code
        await self.subscription_repo.add(subscription)

        if user.plan != tier:
            user.plan = tier
            await self.user_repo.add(user)


def get_billing_service(
    session: AsyncSession = Depends(get_session),
) -> BillingService:
    return BillingService(
        subscription_repo=SubscriptionRepository(session),
        payment_repo=PaymentRepository(session),
        user_repo=UserRepository(session),
        entitlements=get_entitlements_service(session),
        paystack=PaystackClient(),
    )


BillingServiceDep = Annotated[BillingService, Depends(get_billing_service)]
