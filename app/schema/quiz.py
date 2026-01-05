from pydantic import BaseModel, ConfigDict
from typing import List


class QuizRequest(BaseModel):
    curriculum_title: str
    experience_level: str

class Option(BaseModel):
    id: str
    text: str

class Question(BaseModel):
    id: int
    text: str
    options: List[Option]
    correctOptionId: str

class QuizBase(BaseModel):
    questions: List[Question]

class QuizCreate(QuizBase):
    module_id: int

class QuizResponse(QuizBase):
    id: int
    module_id: int

    model_config = ConfigDict(from_attributes=True)
