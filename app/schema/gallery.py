from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict

from .project import ProjectSummary


class GalleryCourseCard(BaseModel):
    """Summary of a published course, safe to serve unauthenticated."""

    id: int
    slug: str
    title: str
    description: str | None = None
    level: str | None = None
    module_count: int = 0
    lesson_count: int = 0
    topic_count: int = 0
    learner_count: int = 0
    author_name: str | None = None
    is_featured: bool = False
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GalleryTopicOutline(BaseModel):
    title: str
    description: str | None = None


class GalleryLessonOutline(BaseModel):
    title: str
    estimated_time: str | None = None
    topics: List[GalleryTopicOutline] = []


class GalleryModuleOutline(BaseModel):
    title: str
    description: str | None = None
    order: int
    lessons: List[GalleryLessonOutline] = []


class GalleryCourseDetail(GalleryCourseCard):
    objectives: List[str] = []
    modules: List[GalleryModuleOutline] = []
    # Title + summary only; the full brief stays behind enrolment.
    capstone: ProjectSummary | None = None


class PublishRequest(BaseModel):
    is_public: bool


class PublishResponse(BaseModel):
    id: int
    is_public: bool
    slug: str | None = None
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EnrollResponse(BaseModel):
    playlist_id: int
    slug: str
    already_enrolled: bool
