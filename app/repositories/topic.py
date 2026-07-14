from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic
from app.models.progress import UserTopicProgress


class TopicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, topic_model):
        self.session.add(topic_model)
        await self.session.flush()
        return topic_model

    async def get_topic_by_id(self, topic_id: int) -> Topic | None:
        result = await self.session.execute(
            select(Topic).where(Topic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def update_youtube_video_id(self, topic_id: int, video_id: str) -> Topic | None:
        topic = await self.get_topic_by_id(topic_id)
        if topic:
            topic.youtube_video_id = video_id
            await self.session.flush()
        return topic

    async def get_topic_progress(self, user_id: UUID, topic_id: int) -> UserTopicProgress | None:
        result = await self.session.execute(
            select(UserTopicProgress).where(
                UserTopicProgress.user_id == user_id,
                UserTopicProgress.topic_id == topic_id
            )
        )
        return result.scalar_one_or_none()
