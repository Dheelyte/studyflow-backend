import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..dependencies.auth import AuthUserDep
from ..dependencies.billing import PlanCurrentUserDep
from ..db.session import db_session
from ..schema.chat import (
    ChatMessagesPage,
    ChatSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from ..services.chat import ChatServiceDep
from ..services.entitlements import METRIC_CHAT_MESSAGES, EntitlementsServiceDep


router = APIRouter(tags=["Chat"], dependencies=[Depends(db_session)])


@router.get("/topics/{topic_id}/chat", response_model=ChatSessionResponse)
async def get_chat_session(
    topic_id: int,
    auth_user: AuthUserDep,
    chat_service: ChatServiceDep,
):
    return await chat_service.get_session_for_topic(auth_user.id, topic_id)


@router.get("/topics/{topic_id}/chat/messages", response_model=ChatMessagesPage)
async def list_chat_messages(
    topic_id: int,
    auth_user: AuthUserDep,
    chat_service: ChatServiceDep,
    before_id: int | None = Query(None, description="Return messages older than this id"),
    limit: int = Query(50, ge=1, le=100),
):
    return await chat_service.get_messages_page(
        user_id=auth_user.id,
        topic_id=topic_id,
        before_id=before_id,
        limit=limit,
    )


@router.delete("/topics/{topic_id}/chat", status_code=204)
async def clear_chat_session(
    topic_id: int,
    auth_user: AuthUserDep,
    chat_service: ChatServiceDep,
):
    await chat_service.clear_session(auth_user.id, topic_id)


@router.post("/topics/{topic_id}/chat/messages", response_model=SendMessageResponse)
async def send_chat_message(
    topic_id: int,
    body: SendMessageRequest,
    auth_user: PlanCurrentUserDep,
    chat_service: ChatServiceDep,
    entitlements: EntitlementsServiceDep,
):
    await entitlements.check_and_increment(auth_user, METRIC_CHAT_MESSAGES)
    return await chat_service.send_message(
        user_id=auth_user.id,
        topic_id=topic_id,
        content=body.content,
        video_timestamp=body.video_timestamp,
    )


@router.post("/topics/{topic_id}/chat/messages/stream")
async def stream_chat_message(
    topic_id: int,
    body: SendMessageRequest,
    auth_user: PlanCurrentUserDep,
    chat_service: ChatServiceDep,
    entitlements: EntitlementsServiceDep,
):
    """Stream the assistant reply as newline-delimited JSON events."""
    # Charge before the stream opens so the client gets a clean 402, not a broken stream.
    await entitlements.check_and_increment(auth_user, METRIC_CHAT_MESSAGES)

    async def event_stream():
        async for event in chat_service.send_message_stream(
            user_id=auth_user.id,
            topic_id=topic_id,
            content=body.content,
            video_timestamp=body.video_timestamp,
        ):
            yield (json.dumps(event, default=str) + "\n").encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
