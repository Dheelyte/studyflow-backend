from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UUID,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Project(Base):
    """A buildable milestone attached to a course, or to one module of it.

    module_id is NULL for the course capstone and set for a module practice build.
    The brief belongs to the course, not the learner , two people taking the same
    published course build the same thing, and their progress is tracked separately
    in UserProjectProgress.
    """

    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey('playlists.id'), index=True)
    module_id: Mapped[int | None] = mapped_column(
        ForeignKey('modules.id'), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String)
    # Short and safe to show on the public course page; brief stays behind enrolment.
    summary: Mapped[str] = mapped_column(String)
    brief: Mapped[str] = mapped_column(String)
    estimated_time: Mapped[str] = mapped_column(String, default="")
    requirements: Mapped[list[dict]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # One practice build per module.
        UniqueConstraint('playlist_id', 'module_id', name='unique_playlist_module_project'),
        # The constraint above does not cover the capstone: NULL module_ids compare as
        # distinct, so without this a course could accumulate several capstones.
        Index(
            'uq_projects_capstone_per_playlist',
            'playlist_id',
            unique=True,
            postgresql_where=text('module_id IS NULL'),
            sqlite_where=text('module_id IS NULL'),
        ),
    )


class UserProjectProgress(Base):
    __tablename__ = 'user_project_progress'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)

    # Requirement ids the learner has ticked. A JSON list is enough for 3–10 items.
    completed_requirement_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    submission_url: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project = relationship("Project", lazy="raise")

    __table_args__ = (
        UniqueConstraint('user_id', 'project_id', name='unique_user_project_progress'),
    )
