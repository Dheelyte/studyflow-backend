from fastapi import APIRouter, Depends

from ..dependencies.auth import AuthUserDep
from ..db.session import db_session
from ..schema.topic import TopicVideoResponse, TopicExplainRequest, TopicExplainResponse
from ..services.topic import TopicServiceDep


router = APIRouter(
    tags=["Topics"], dependencies=[Depends(db_session)]
)


@router.get("/topics/{topic_id}/video", response_model=TopicVideoResponse)
async def get_topic_video(
    topic_id: int,
    auth_user: AuthUserDep,
    topic_service: TopicServiceDep,
):
    return await topic_service.get_or_fetch_video(topic_id, auth_user.id)


@router.post("/topics/{topic_id}/explain", response_model=TopicExplainResponse)
async def explain_topic(
    topic_id: int,
    body: TopicExplainRequest,
    auth_user: AuthUserDep,
    topic_service: TopicServiceDep,
):
    return await topic_service.explain_topic_at_timestamp(
        topic_id, body.video_id, body.timestamp
    )
