from pydantic import BaseModel, Field
from typing import List


class TopicOutput(BaseModel):
    title: str = Field(..., description="Topic title")
    description: str = Field(
        ...,
        description=(
            "An in-depth, multi-sentence explanation of what this topic covers, "
            "the key concepts the learner will understand, the prerequisites or "
            "intuitions the learner should leave with, and how this topic connects "
            "to the broader lesson and module. Should read as a substantive paragraph "
            "of at least 3-5 sentences, not a short one-liner."
        ),
    )


class Lesson(BaseModel):
    lesson_title: str
    estimated_time: str
    topics: List[TopicOutput]


class Module(BaseModel):
    module_id: int
    module_title: str
    lessons: List[Lesson]


class Curriculum(BaseModel):
    curriculum_title: str
    overview: str
    learning_objectives: List[str]
    modules: List[Module]


# Input model for the user request
class CurriculumRequest(BaseModel):
    topic: str
