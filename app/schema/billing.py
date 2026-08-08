from datetime import datetime

from pydantic import BaseModel


class PlanLimitsRead(BaseModel):
    course_generations_monthly: int
    chat_messages_daily: int
    screen_tutor_daily: int


class MetricUsage(BaseModel):
    used: int
    limit: int
    period: str  # "daily" | "monthly"


class UsageRead(BaseModel):
    course_generations: MetricUsage
    chat_messages: MetricUsage
    screen_tutor_questions: MetricUsage


class SubscriptionRead(BaseModel):
    tier: str
    status: str
    interval: str
    current_period_end: datetime | None = None

    model_config = {"from_attributes": True}


class BillingStatus(BaseModel):
    plan: str
    limits: PlanLimitsRead
    usage: UsageRead
    subscription: SubscriptionRead | None = None


class CheckoutRequest(BaseModel):
    tier: str  # "pro" | "max"
    interval: str  # "monthly" | "annual"


class CheckoutResponse(BaseModel):
    authorization_url: str
    reference: str


class VerifyResponse(BaseModel):
    status: str  # "success" | "pending" | "failed"
    plan: str
