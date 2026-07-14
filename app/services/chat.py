import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..repositories.chat import ChatRepository
from ..repositories.topic import TopicRepository
from ..models.chat import ChatRole
from ..schema.chat import (
    ChatMessageRead,
    ChatMessagesPage,
    ChatSessionResponse,
    SendMessageResponse,
)
from ..chains.chat_with_tutor import chat_with_tutor, chat_with_tutor_stream
from ..services.transcript import TranscriptService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        topic_repo: TopicRepository,
    ):
        self.chat_repo = chat_repo
        self.topic_repo = topic_repo

    DEFAULT_PAGE_SIZE = 50

    async def get_session_for_topic(self, user_id: UUID, topic_id: int) -> ChatSessionResponse:
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        session = await self.chat_repo.get_or_create_session(user_id, topic_id)
        messages, has_more = await self.chat_repo.list_messages_page(
            session.id, before_id=None, limit=self.DEFAULT_PAGE_SIZE
        )
        return ChatSessionResponse(
            session_id=session.id,
            topic_id=topic_id,
            messages=[ChatMessageRead.model_validate(m) for m in messages],
            has_more=has_more,
        )

    async def get_messages_page(
        self,
        user_id: UUID,
        topic_id: int,
        before_id: int | None,
        limit: int,
    ) -> ChatMessagesPage:
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        session = await self.chat_repo.get_session(user_id, topic_id)
        if not session:
            return ChatMessagesPage(messages=[], has_more=False)

        messages, has_more = await self.chat_repo.list_messages_page(
            session.id, before_id=before_id, limit=limit
        )
        return ChatMessagesPage(
            messages=[ChatMessageRead.model_validate(m) for m in messages],
            has_more=has_more,
        )

    async def clear_session(self, user_id: UUID, topic_id: int) -> None:
        session = await self.chat_repo.get_session(user_id, topic_id)
        if session:
            await self.chat_repo.clear_messages(session.id)

    async def send_message(
        self,
        user_id: UUID,
        topic_id: int,
        content: str,
        video_timestamp: float | None,
    ) -> SendMessageResponse:
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        session = await self.chat_repo.get_or_create_session(user_id, topic_id)

        user_msg = await self.chat_repo.add_message(
            session_id=session.id,
            role=ChatRole.USER,
            content=content,
            video_timestamp=video_timestamp,
        )

        # Pull only the most recent slice of history into the LLM prompt so the
        # context stays bounded as the conversation grows.
        history_page, _ = await self.chat_repo.list_messages_page(
            session.id, before_id=None, limit=self.DEFAULT_PAGE_SIZE
        )
        history_for_prompt = [m for m in history_page if m.id != user_msg.id]

        transcript_excerpt: str | None = None
        if video_timestamp is not None and topic.youtube_video_id:
            try:
                transcript_excerpt = await TranscriptService().get_transcript_window(
                    topic.youtube_video_id, video_timestamp
                )
                print(
                    f"\n[transcript] video={topic.youtube_video_id} "
                    f"t={video_timestamp:.1f}s\n{transcript_excerpt}\n",
                    flush=True,
                )
            except Exception:
                logger.exception(
                    "Failed to fetch transcript for video %s at %s",
                    topic.youtube_video_id,
                    video_timestamp,
                )
                transcript_excerpt = None

        reply = await chat_with_tutor(
            topic_title=topic.title,
            topic_description=topic.description,
            history=history_for_prompt,
            user_message=content,
            transcript_excerpt=transcript_excerpt,
            video_timestamp=video_timestamp,
        )

        assistant_msg = await self.chat_repo.add_message(
            session_id=session.id,
            role=ChatRole.ASSISTANT,
            content=reply,
            video_timestamp=video_timestamp,
        )

        return SendMessageResponse(
            user_message=ChatMessageRead.model_validate(user_msg),
            assistant_message=ChatMessageRead.model_validate(assistant_msg),
        )

    async def send_message_stream(
        self,
        user_id: UUID,
        topic_id: int,
        content: str,
        video_timestamp: float | None,
    ):
        """Yield event dicts as the assistant reply streams.

        Event shapes:
          {"type": "user_message", "message": <ChatMessageRead>}
          {"type": "chunk", "text": <str>}
          {"type": "done", "message": <ChatMessageRead>}
          {"type": "error", "error": <str>}
        """
        topic = await self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        session = await self.chat_repo.get_or_create_session(user_id, topic_id)

        user_msg = await self.chat_repo.add_message(
            session_id=session.id,
            role=ChatRole.USER,
            content=content,
            video_timestamp=video_timestamp,
        )

        # Emit the user message immediately so the client can swap the optimistic
        # row right away — don't wait for transcript / history fetches.
        yield {
            "type": "user_message",
            "message": ChatMessageRead.model_validate(user_msg).model_dump(mode="json"),
        }

        # Run history and transcript fetches concurrently to minimize TTFT.
        async def _fetch_transcript() -> str | None:
            if video_timestamp is None or not topic.youtube_video_id:
                return None
            try:
                excerpt = await asyncio.wait_for(
                    TranscriptService().get_transcript_window(
                        topic.youtube_video_id, video_timestamp
                    ),
                    timeout=2.5,
                )
                print(
                    f"\n[transcript] video={topic.youtube_video_id} "
                    f"t={video_timestamp:.1f}s\n{excerpt}\n",
                    flush=True,
                )
                return excerpt
            except asyncio.TimeoutError:
                logger.warning(
                    "Transcript fetch timed out for video %s at %s",
                    topic.youtube_video_id,
                    video_timestamp,
                )
                return None
            except Exception:
                logger.exception(
                    "Failed to fetch transcript for video %s at %s",
                    topic.youtube_video_id,
                    video_timestamp,
                )
                return None

        history_task = asyncio.create_task(
            self.chat_repo.list_messages_page(
                session.id, before_id=None, limit=self.DEFAULT_PAGE_SIZE
            )
        )
        transcript_task = asyncio.create_task(_fetch_transcript())

        history_page, _ = await history_task
        history_for_prompt = [m for m in history_page if m.id != user_msg.id]
        transcript_excerpt = await transcript_task

        full_reply = ""
        try:
            async for chunk in chat_with_tutor_stream(
                topic_title=topic.title,
                topic_description=topic.description,
                history=history_for_prompt,
                user_message=content,
                transcript_excerpt=transcript_excerpt,
                video_timestamp=video_timestamp,
            ):
                full_reply += chunk
                yield {"type": "chunk", "text": chunk}
        except Exception as e:
            logger.exception("Streaming chat error")
            if not full_reply:
                full_reply = "I'm sorry, I couldn't generate a reply right now. Please try again."
            yield {"type": "error", "error": str(e)}

        assistant_msg = await self.chat_repo.add_message(
            session_id=session.id,
            role=ChatRole.ASSISTANT,
            content=full_reply,
            video_timestamp=video_timestamp,
        )

        yield {
            "type": "done",
            "message": ChatMessageRead.model_validate(assistant_msg).model_dump(
                mode="json"
            ),
        }


def get_chat_repo(session: AsyncSession = Depends(get_session)):
    return ChatRepository(session)


def get_topic_repo_for_chat(session: AsyncSession = Depends(get_session)):
    return TopicRepository(session)


def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repo),
    topic_repo: TopicRepository = Depends(get_topic_repo_for_chat),
):
    return ChatService(chat_repo, topic_repo)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
