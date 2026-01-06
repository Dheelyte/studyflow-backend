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

class QuizSubmission(BaseModel):
    # Map question_id (int) to selected_option_id (str)
    answers: dict[int, str]
    questions: List[Question] # Stateless verification: client sends back the questions


class QuizBase(BaseModel):
    questions: List[Question]

class QuizCreate(QuizBase):
    module_id: int

class QuizSubmissionResponse(BaseModel):
    passed: bool
