from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, ChatMessage, ChatRole


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_session(self, user_id: UUID, topic_id: int) -> ChatSession | None:
        result = await self.session.execute(
            select(ChatSession).where(
                ChatSession.user_id == user_id,
                ChatSession.topic_id == topic_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_session(self, user_id: UUID, topic_id: int) -> ChatSession:
        existing = await self.get_session(user_id, topic_id)
        if existing:
            return existing
        chat_session = ChatSession(user_id=user_id, topic_id=topic_id)
        self.session.add(chat_session)
        await self.session.flush()
        return chat_session

    async def list_messages(self, session_id: int) -> list[ChatMessage]:
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return list(result.scalars().all())

    async def list_messages_page(
        self,
        session_id: int,
        before_id: int | None = None,
        limit: int = 50,
    ) -> tuple[list[ChatMessage], bool]:
        """Return the most recent ``limit`` messages older than ``before_id``.

        Messages are returned in chronological (ascending) order. ``has_more``
        is True when there are still older messages beyond this page.
        """
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
        if before_id is not None:
            stmt = stmt.where(ChatMessage.id < before_id)
        stmt = stmt.order_by(ChatMessage.id.desc()).limit(limit + 1)

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        page = rows[:limit]
        page.reverse()
        return page, has_more

    async def clear_messages(self, session_id: int) -> None:
        await self.session.execute(
            delete(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        await self.session.flush()

    async def add_message(
        self,
        session_id: int,
        role: ChatRole,
        content: str,
        video_timestamp: float | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            video_timestamp=video_timestamp,
        )
        self.session.add(message)
        await self.session.flush()
        return message
