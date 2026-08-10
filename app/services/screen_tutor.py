import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..chains.screen_tutor import screen_tutor_stream
from ..db.session import get_session
from ..exceptions.base import BadRequestError
from ..models.user import User
from ..repositories.screen_tutor import ScreenTutorRepository
from ..services.entitlements import get_limits
from ..schema.screen_tutor import (
    AnswerStyle,
    PinTarget,
    PinTargetList,
    ScreenAskRequest,
    ScreenTutorStatus,
)

logger = logging.getLogger(__name__)

# Data URLs inflate bytes by ~33%; anything larger than this should have been
# downscaled client-side and would risk the API gateway payload limit.
MAX_IMAGE_CHARS = 6_000_000


class ScreenTutorService:
    def __init__(self, repo: ScreenTutorRepository):
        self.repo = repo

    @staticmethod
    def daily_limit_for(user: User) -> int:
        return get_limits(user.plan).screen_tutor_daily

    async def get_status(self, user: User) -> ScreenTutorStatus:
        usage = await self.repo.get_usage(user.id)
        used = usage.question_count if usage else 0
        limit = self.daily_limit_for(user)
        return ScreenTutorStatus(
            used_today=used,
            daily_limit=limit,
            remaining=max(0, limit - used),
        )

    async def get_pin_targets(self, playlist_id: int) -> PinTargetList:
        course_title, topics, projects = await self.repo.get_pin_targets(playlist_id)

        targets = [
            PinTarget(kind="topic", id=t[0], label=t[1], sublabel=t[2])
            for t in topics
        ]
        targets += [
            PinTarget(
                kind="project",
                id=p[0],
                label=p[1],
                sublabel="Capstone project" if p[2] is None else "Practice build",
            )
            for p in projects
        ]
        return PinTargetList(course_title=course_title, targets=targets)

    async def _build_context(self, payload: ScreenAskRequest) -> dict:
        context: dict = {}
        if payload.topic_id:
            context.update(await self.repo.get_topic_context(payload.topic_id))
        if payload.project_id:
            context.update(await self.repo.get_project_context(payload.project_id))
        return context

    async def ask_stream(self, user: User, payload: ScreenAskRequest):
        """Yield NDJSON-friendly events. The frame is forwarded, never stored.

        Events: {"type": "status", ...} | {"type": "chunk", "text": ...}
                | {"type": "done", ...} | {"type": "error", "error": ...}
        """
        if not payload.image.startswith("data:image/"):
            yield {"type": "error", "error": "Expected an image data URL."}
            return

        if payload.region_image and not payload.region_image.startswith("data:image/"):
            yield {"type": "error", "error": "Expected an image data URL for the highlighted area."}
            return

        if payload.audio and not payload.audio.startswith("data:audio/"):
            yield {"type": "error", "error": "Expected an audio data URL for the spoken question."}
            return

        total_chars = (
            len(payload.image) + len(payload.region_image or "") + len(payload.audio or "")
        )
        if total_chars > MAX_IMAGE_CHARS:
            yield {
                "type": "error",
                "error": "That screenshot is too large. Try sharing a single window instead of the whole screen.",
            }
            return

        # Check and charge in one atomic step, so parallel requests at the cap
        # can't all slip through the old check-then-increment gap.
        daily_limit = self.daily_limit_for(user)
        if not await self.repo.try_consume(user.id, daily_limit):
            yield {
                "type": "error",
                "error": (
                    f"You've used all {daily_limit} screen questions for today. "
                    "Your quota resets at midnight UTC."
                ),
                "quota_exhausted": True,
            }
            return

        status = await self.get_status(user)
        yield {"type": "status", "remaining": status.remaining, "daily_limit": daily_limit}

        context = await self._build_context(payload)

        full_reply = ""
        try:
            async for chunk in screen_tutor_stream(
                image_data_url=payload.image,
                region_data_url=payload.region_image,
                audio_data_url=payload.audio,
                question=payload.question,
                answer_style=payload.answer_style,
                context=context,
            ):
                full_reply += chunk
                yield {"type": "chunk", "text": chunk}
        except Exception as e:
            logger.exception("Screen tutor streaming error")
            yield {"type": "error", "error": str(e)}
            return

        yield {
            "type": "done",
            "answer": full_reply,
            "remaining": remaining,
            "answer_style": payload.answer_style.value,
        }


def get_screen_tutor_repo(session: AsyncSession = Depends(get_session)) -> ScreenTutorRepository:
    return ScreenTutorRepository(session)


def get_screen_tutor_service(
    repo: ScreenTutorRepository = Depends(get_screen_tutor_repo),
) -> ScreenTutorService:
    return ScreenTutorService(repo)


ScreenTutorServiceDep = Annotated[ScreenTutorService, Depends(get_screen_tutor_service)]
