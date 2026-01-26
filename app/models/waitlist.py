from sqlalchemy import String, DateTime
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import func
from .base import Base

class Waitlist(Base):
    __tablename__ = "waitlist"

    email = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<Waitlist {self.email}>"
