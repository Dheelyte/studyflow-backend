from datetime import datetime, timezone

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UUID, Integer, String, DateTime, ForeignKey, Table, Text, Column, func

from .base import Base


# Association table for User-Community many-to-many relationship
# Note: Using Column() for Table definition as mapped_column() is for Declarative mappings
community_members = Table(
    "community_members",
    Base.metadata,
    Column("user_id", UUID, ForeignKey("users.id"), primary_key=True),
    Column("community_id", Integer, ForeignKey("communities.id"), primary_key=True),
    Column("joined_at", DateTime, default=lambda: datetime.now(timezone.utc))
)


class Community(Base):
    __tablename__ = "communities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Relationships
    posts = relationship("Post", back_populates="community", cascade="all, delete-orphan")
    members = relationship("User", secondary=community_members, back_populates="communities")
