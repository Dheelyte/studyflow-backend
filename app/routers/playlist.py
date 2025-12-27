from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated

from ..dependencies.auth import AuthUserDep
from ..schema.playlist import PlaylistCreate, PlaylistResponse
from ..schema.progress import UserPlaylistResponse
from ..db.session import db_session
from ..schema.resource import Curriculum, CurriculumRequest
from ..chains.generate_curriculum import generate_curriculum_response
from ..services.playlist import PlaylistServiceDep


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


@router.post('/playlists', response_model=PlaylistResponse)
async def create_playlist(
    playlist_data: PlaylistCreate,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    new_playlist = await playlist_service.create_playlist_from_curriculum(playlist_data, auth_user.id)
    return new_playlist


@router.get('/playlists/{playlist_id}', response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: int,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    playlist = await playlist_service.get_playlist(playlist_id)
    return playlist


@router.get('/playlists', response_model=list[UserPlaylistResponse])
async def get_user_playlists(
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    playlists = await playlist_service.get_user_playlists(auth_user.id)
    return playlists


@router.post('/resource/{resource_id}', response_model=list[UserPlaylistResponse])
async def update_resource_status(
    resource_id: int,
    auth_user: AuthUserDep,
    playlist_service: PlaylistServiceDep
):
    await playlist_service.update_resource_status(resource_id, auth_user.id)
    return {"message": "resource status updated"}
