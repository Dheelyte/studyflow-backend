from fastapi import APIRouter, Depends, Query
from typing import Annotated

from ..db.session import db_session
from ..schema.resource import Curriculum, CurriculumRequest
from ..chains.generate_curriculum import generate_curriculum_response


router = APIRouter(
    tags=["Curriculum"], dependencies=[Depends(db_session)]
)


@router.get("/generate-curriculum", response_model=Curriculum)
async def generate_curriculum(request: Annotated[CurriculumRequest, Query()]):

    curriculum = generate_curriculum_response(
        topic=request.topic,
        experience_level=request.experience_level,
        duration=request.duration
    )

    return curriculum
