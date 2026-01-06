from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated

from ..dependencies.auth import AuthUserDep
from ..schema.playlist import PlaylistCreate, PlaylistResponse, PlaylistDetailSchema
from ..schema.progress import UserPlaylistResponse, UserResourceProgressResponse
from ..db.session import db_session
from ..schema.resource import Curriculum, CurriculumRequest
from ..chains.generate_curriculum import generate_curriculum_response
from ..services.playlist import PlaylistServiceDep
from ..schema.quiz import QuizSubmission, QuizSubmissionResponse, QuizBase, QuizRequest


router = APIRouter(
    tags=["Curriculum"], dependencies=[Depends(db_session)]
)

@router.get("/generate-curriculum", response_model=Curriculum)
async def generate_curriculum(request: Annotated[CurriculumRequest, Query()]):
    curriculum = await generate_curriculum_response(
        topic=request.topic,
        experience_level=request.experience_level,
        duration=request.duration
    )
    return curriculum


@router.post('/playlists', response_model=PlaylistResponse)
async def create_playlist(
    playlist_data: PlaylistCreate,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    new_playlist = await playlist_service.create_playlist_from_curriculum(playlist_data, auth_user.id)
    return new_playlist


@router.get('/playlists/{playlist_id}', response_model=PlaylistDetailSchema)
async def get_playlist(
    playlist_id: int,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    playlist = await playlist_service.get_playlist_details(playlist_id, auth_user.id)
    return playlist


@router.get('/playlists', response_model=list[UserPlaylistResponse])
async def get_user_playlists(
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    playlists = await playlist_service.get_user_playlists(auth_user.id)
    return playlists


@router.post('/resource/{resource_id}/complete', response_model=UserResourceProgressResponse)
async def mark_resource_completed(
    resource_id: int,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    progress = await playlist_service.mark_resource_completed(resource_id, auth_user.id)
    if not progress:
        raise HTTPException(status_code=404, detail="Resource not found")
    return progress


@router.get('/modules/{module_id}/quiz', response_model=QuizBase)
async def generate_quiz(
    quiz_data: Annotated[QuizRequest, Query()],
    module_id: int,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    quiz = await playlist_service.generate_module_quiz(
        module_id=module_id,
        curriculum_title=quiz_data.curriculum_title,
        experience_level=quiz_data.experience_level
    )
    return quiz


@router.post('/modules/{module_id}/quiz/submit', response_model=QuizSubmissionResponse)
async def submit_quiz(
    module_id: int,
    submission: QuizSubmission,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    result = await playlist_service.submit_quiz(module_id, submission, auth_user.id)
    if not result:
        # If quiz doesn't exist, maybe 404
        raise HTTPException(status_code=404, detail="Quiz not found")
    return result




# @router.get('/modules/{module_id}/quiz', response_model=QuizResponse | None)
# async def get_module_quiz(
#     module_id: int,
#     auth_user: AuthUserDep,
#     playlist_service: PlaylistServiceDep
# ):
#     quiz = await playlist_service.get_quiz_by_module_id(module_id)
#     if not quiz:
#         raise HTTPException(status_code=404, detail="Quiz not found")
#     return quiz
