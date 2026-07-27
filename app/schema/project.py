from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ProjectRequirement(BaseModel):
    id: int = Field(description="Stable 1-based index for this requirement")
    text: str = Field(description="One concrete, checkable requirement")


class ProjectBrief(BaseModel):
    """Shape the LLM must return."""

    title: str = Field(description="Short name for the thing being built, max 8 words")
    summary: str = Field(
        description="One sentence describing what the learner will build, safe to show publicly"
    )
    brief: str = Field(
        description="The full brief: context, what to build, and how to approach it"
    )
    estimated_time: str = Field(description="Rough effort estimate, e.g. '4 hours'")
    requirements: List[ProjectRequirement] = Field(
        description="Concrete checkable requirements"
    )


class ProjectProgressRead(BaseModel):
    completed_requirement_ids: List[int] = []
    submission_url: str | None = None
    notes: str | None = None
    is_completed: bool = False
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectRead(BaseModel):
    id: int
    playlist_id: int
    module_id: int | None = None
    is_capstone: bool = False
    title: str
    summary: str
    brief: str
    estimated_time: str | None = None
    requirements: List[ProjectRequirement] = []
    xp_reward: int = 0
    progress: ProjectProgressRead = ProjectProgressRead()

    model_config = ConfigDict(from_attributes=True)


class ProjectSummary(BaseModel):
    """Public-safe teaser for the course page — no brief, no requirements."""

    title: str
    summary: str
    estimated_time: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectProgressUpdate(BaseModel):
    completed_requirement_ids: List[int] | None = None
    submission_url: str | None = None
    notes: str | None = None
