from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CertificateRead(BaseModel):
    id: int
    user_id: UUID
    playlist_id: int
    playlist_title: str
    recipient_name: str
    verification_code: str
    issued_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificatePublic(BaseModel):
    """Public view exposed by verification , no user_id leaked."""
    playlist_title: str
    playlist_id: int
    recipient_name: str
    verification_code: str
    issued_at: datetime


class CertificateEligibility(BaseModel):
    eligible: bool
    completed_topics: int
    total_topics: int
    passed_quizzes: int
    total_modules: int
    certificate: CertificateRead | None = None
