from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class User(Base):
    __tablename__ = "users"

    email = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash = mapped_column(String(255), nullable=False)
    first_name = mapped_column(String(255), nullable=False)
    last_name = mapped_column(String(255), nullable=False)
    is_active = mapped_column(Boolean, default=True)
    is_verified = mapped_column(Boolean, default=False)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<User {self.email}>"
    

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    code_hash = mapped_column(String(255), nullable=False, index=True)
    user_id = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    is_used = mapped_column(Boolean, default=False, nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", lazy="joined")

    def __repr__(self):
        return f"<ResetToken user_id={self.user_id} is_used={self.is_used}>"
