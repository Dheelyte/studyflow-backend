import json
import logging

from fastapi import APIRouter, Depends, Query, Request, Response, status

from ..db.session import db_session
from ..dependencies.auth import AuthUserDep
from ..rate_limit import limiter
from ..schema.billing import (
    BillingStatus,
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionRead,
    VerifyResponse,
)
from ..services.billing import BillingServiceDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Billing"], dependencies=[Depends(db_session)])


@router.get("/billing/status", response_model=BillingStatus)
async def get_billing_status(auth_user: AuthUserDep, service: BillingServiceDep):
    return await service.status(auth_user)


@router.post("/billing/checkout", response_model=CheckoutResponse)
async def start_checkout(
    body: CheckoutRequest,
    auth_user: AuthUserDep,
    service: BillingServiceDep,
):
    return await service.checkout(auth_user, body.tier, body.interval)


@router.get("/billing/verify", response_model=VerifyResponse)
async def verify_checkout(
    auth_user: AuthUserDep,
    service: BillingServiceDep,
    reference: str = Query(min_length=1),
):
    """Callback-page fallback in case the webhook hasn't landed yet."""
    return await service.verify(auth_user, reference)


@router.post("/billing/cancel", response_model=SubscriptionRead)
async def cancel_subscription(auth_user: AuthUserDep, service: BillingServiceDep):
    return await service.cancel(auth_user)


# Separate router: the webhook is called by Paystack, not a browser , no auth,
# and exempt from the global rate limit so webhook retries never 429 (behind
# API Gateway all callers can collapse onto one rate-limit key).
webhook_router = APIRouter(tags=["Billing"], dependencies=[Depends(db_session)])


@webhook_router.post("/billing/webhook/paystack")
@limiter.exempt
async def paystack_webhook(request: Request, service: BillingServiceDep):
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    if not service.paystack.verify_signature(raw_body, signature):
        logger.warning("Paystack webhook rejected: bad signature")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    await service.handle_webhook(event)
    return {"status": "ok"}
