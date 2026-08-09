import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..db.session import db_session
from ..dependencies.auth import AuthUserDep
from ..dependencies.billing import PlanCurrentUserDep
from ..dependencies.playlist import PlaylistIdDep
from ..schema.screen_tutor import PinTargetList, ScreenAskRequest, ScreenTutorStatus
from ..services.screen_tutor import ScreenTutorServiceDep


router = APIRouter(tags=["Screen Tutor"], dependencies=[Depends(db_session)])


@router.get("/playlists/{playlist_ref}/tutor-targets", response_model=PinTargetList)
async def get_tutor_pin_targets(
    playlist_id: PlaylistIdDep,
    auth_user: AuthUserDep,
    service: ScreenTutorServiceDep,
):
    """Lessons and existing projects the learner can pin the screen tutor to."""
    return await service.get_pin_targets(playlist_id)


@router.get("/screen-tutor/status", response_model=ScreenTutorStatus)
async def get_screen_tutor_status(
    auth_user: PlanCurrentUserDep,
    service: ScreenTutorServiceDep,
):
    """Remaining screen questions for today."""
    return await service.get_status(auth_user)


@router.post("/screen-tutor/ask")
async def ask_about_screen(
    body: ScreenAskRequest,
    auth_user: PlanCurrentUserDep,
    service: ScreenTutorServiceDep,
):
    """Answer a question about the learner's screen, streamed as newline-delimited JSON.

    The frame is forwarded to the model and never persisted.
    """

    async def event_stream():
        async for event in service.ask_stream(auth_user, body):
            yield (json.dumps(event, default=str) + "\n").encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
