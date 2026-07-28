from enum import Enum

from pydantic import BaseModel, Field


class AnswerStyle(str, Enum):
    HINT = "hint"
    DIRECT = "direct"


class ScreenAskRequest(BaseModel):
    # A data URL (data:image/jpeg;base64,...). The frame is forwarded to the model
    # and then dropped — it is never persisted.
    image: str = Field(min_length=32)
    # Optional crop of the area the learner highlighted, at native resolution.
    region_image: str | None = Field(default=None, min_length=32)
    question: str = Field(default="", max_length=2000)
    # Spoken question as a data URL (data:audio/wav;base64,...). Gemini takes audio
    # natively, so there is no separate transcription step.
    audio: str | None = Field(default=None, min_length=32)
    answer_style: AnswerStyle = AnswerStyle.HINT
    # What the learner pinned, or the lesson the widget auto-followed.
    topic_id: int | None = None
    project_id: int | None = None


class PinTarget(BaseModel):
    """Something the learner can point the tutor at."""

    kind: str  # "topic" | "project"
    id: int
    label: str
    sublabel: str | None = None


class PinTargetList(BaseModel):
    course_title: str | None = None
    targets: list[PinTarget] = []


class ScreenTutorStatus(BaseModel):
    used_today: int
    daily_limit: int
    remaining: int
