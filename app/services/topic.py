from typing import Annotated
from uuid import UUID
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..repositories.topic import TopicRepository
from ..services.youtube import YouTubeService
from ..schema.topic import TopicVideoResponse, TopicExplainResponse


class TopicService:
    def __init__(
        self,
        topic_repo: TopicRepository,
        youtube_service: YouTubeService,
    ):
        self.topic_repo = topic_repo
        self.youtube_service = youtube_service

    async def get_or_fetch_video(self, topic_id: int, user_id: UUID | None = None) -> TopicVideoResponse:
        """Fetch-once, save-forever pattern for YouTube video IDs."""
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        is_completed = False
        if user_id:
            progress = await self.topic_repo.get_topic_progress(user_id, topic_id)
            is_completed = bool(progress and progress.is_completed)

        # Return cached video ID if it exists
        if topic.youtube_video_id:
            return TopicVideoResponse(
                topic_id=topic.id,
                youtube_video_id=topic.youtube_video_id,
                title=topic.title,
                description=topic.description,
                is_completed=is_completed,
            )

        # JIT fetch from YouTube API
        video_id = await self.youtube_service.search_video(topic.title)
        if not video_id:
            raise HTTPException(status_code=404, detail="No suitable video found for this topic")

        # Save to database
        await self.topic_repo.update_youtube_video_id(topic.id, video_id)

        return TopicVideoResponse(
            topic_id=topic.id,
            youtube_video_id=video_id,
            title=topic.title,
            description=topic.description,
            is_completed=is_completed,
        )

    async def explain_topic_at_timestamp(
        self, topic_id: int, video_id: str, timestamp: float
    ) -> TopicExplainResponse:
        """Fetch transcript around timestamp and generate AI explanation."""
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        # Import here to avoid circular imports and keep service flexible
        from ..services.transcript import TranscriptService
        from ..chains.generate_explanation import generate_explanation

        transcript_service = TranscriptService()

        try:
            transcript_excerpt = await transcript_service.get_transcript_window(
                video_id, timestamp
            )
        except Exception:
            transcript_excerpt = ""

        if not transcript_excerpt:
            # Fallback: generate explanation based on topic title alone
            explanation = await generate_explanation(
                topic_title=topic.title,
                transcript_excerpt=f"(No transcript available. The learner is studying: {topic.description})",
                timestamp=timestamp,
            )
            return TopicExplainResponse(
                explanation=explanation,
                transcript_excerpt=None,
            )

        explanation = await generate_explanation(
            topic_title=topic.title,
            transcript_excerpt=transcript_excerpt,
            timestamp=timestamp,
        )

        return TopicExplainResponse(
            explanation=explanation,
            transcript_excerpt=transcript_excerpt,
        )


def get_topic_repo(session: AsyncSession = Depends(get_session)):
    return TopicRepository(session)


def get_youtube_service():
    return YouTubeService()


def get_topic_service(
    topic_repo: TopicRepository = Depends(get_topic_repo),
    youtube_service: YouTubeService = Depends(get_youtube_service),
):
    return TopicService(topic_repo, youtube_service)


TopicServiceDep = Annotated[TopicService, Depends(get_topic_service)]
