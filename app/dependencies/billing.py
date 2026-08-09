from typing import Annotated

from fastapi import Depends

from ..models.user import User
from ..services.billing import BillingService, get_billing_service
from .auth import AuthUserDep


async def get_plan_current_user(
    auth_user: AuthUserDep,
    billing_service: BillingService = Depends(get_billing_service),
) -> User:
    """The authenticated user, with an expired paid plan reconciled first.

    Use on routes where `user.plan` decides what the user gets — the AI features
    a subscription pays for, and the billing page. Everywhere else should keep
    using AuthUserDep: the check is cheap but pointless on routes that never
    read the plan.

    Costs nothing on the hot path. Free users and anyone whose plan is still
    within its period return after a single in-memory date comparison, since
    `plan_expires_at` rides along on the already-loaded user row.
    """
    await billing_service.reconcile_plan(auth_user)
    return auth_user


PlanCurrentUserDep = Annotated[User, Depends(get_plan_current_user)]
