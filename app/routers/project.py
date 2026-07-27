from fastapi import APIRouter, Depends

from ..db.session import db_session
from ..dependencies.auth import AuthUserDep
from ..dependencies.playlist import PlaylistIdDep
from ..schema.project import ProjectProgressUpdate, ProjectRead
from ..services.project import ProjectServiceDep


router = APIRouter(tags=["Projects"], dependencies=[Depends(db_session)])


@router.get("/playlists/{playlist_ref}/project", response_model=ProjectRead)
async def get_course_capstone(
    playlist_id: PlaylistIdDep,
    auth_user: AuthUserDep,
    service: ProjectServiceDep,
):
    """The course capstone. Generated on first request, then reused."""
    return await service.get_or_create_capstone(playlist_id, auth_user.id)


@router.get("/modules/{module_id}/project", response_model=ProjectRead)
async def get_module_project(
    module_id: int,
    auth_user: AuthUserDep,
    service: ProjectServiceDep,
):
    """The practice build for one module. Generated on first request, then reused."""
    return await service.get_or_create_module_project(module_id, auth_user.id)


@router.patch("/projects/{project_id}/progress", response_model=ProjectRead)
async def update_project_progress(
    project_id: int,
    payload: ProjectProgressUpdate,
    auth_user: AuthUserDep,
    service: ProjectServiceDep,
):
    return await service.update_progress(project_id, auth_user.id, payload)
