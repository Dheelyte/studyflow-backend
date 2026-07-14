from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session
from ..models.certificate import Certificate
from ..repositories.certificate import CertificateRepository
from ..repositories.playlist import PlaylistRepository
from ..repositories.user import UserRepository
from ..schema.certificate import (
    CertificateEligibility,
    CertificatePublic,
    CertificateRead,
)


class CertificateService:
    def __init__(
        self,
        cert_repo: CertificateRepository,
        playlist_repo: PlaylistRepository,
        user_repo: UserRepository,
    ):
        self.cert_repo = cert_repo
        self.playlist_repo = playlist_repo
        self.user_repo = user_repo

    async def get_eligibility(
        self, user_id: UUID, playlist_id: int
    ) -> CertificateEligibility:
        playlist = await self.playlist_repo.get_playlist_by_id(playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        total_topics, completed_topics, total_modules, passed_quizzes = (
            await self.cert_repo.get_playlist_progress_counts(playlist_id, user_id)
        )

        existing = await self.cert_repo.get_by_user_and_playlist(user_id, playlist_id)
        eligible = (
            total_modules > 0
            and total_topics > 0
            and completed_topics >= total_topics
            and passed_quizzes >= total_modules
        )

        return CertificateEligibility(
            eligible=eligible,
            completed_topics=completed_topics,
            total_topics=total_topics,
            passed_quizzes=passed_quizzes,
            total_modules=total_modules,
            certificate=(
                CertificateRead.model_validate(existing) if existing else None
            ),
        )

    async def issue_certificate(
        self, user_id: UUID, playlist_id: int
    ) -> CertificateRead:
        existing = await self.cert_repo.get_by_user_and_playlist(user_id, playlist_id)
        if existing:
            return CertificateRead.model_validate(existing)

        playlist = await self.playlist_repo.get_playlist_by_id(playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        total_topics, completed_topics, total_modules, passed_quizzes = (
            await self.cert_repo.get_playlist_progress_counts(playlist_id, user_id)
        )
        eligible = (
            total_modules > 0
            and total_topics > 0
            and completed_topics >= total_topics
            and passed_quizzes >= total_modules
        )
        if not eligible:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Not eligible for certificate. Complete every topic and pass "
                    "every module quiz first."
                ),
            )

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        recipient_name = (
            f"{user.first_name} {user.last_name}".strip() or user.email
        )

        cert = Certificate(
            user_id=user_id,
            playlist_id=playlist_id,
            playlist_title=playlist.title,
            recipient_name=recipient_name,
        )
        await self.cert_repo.create(cert)
        return CertificateRead.model_validate(cert)

    async def get_by_code_public(self, code: str) -> CertificatePublic:
        cert = await self.cert_repo.get_by_code(code)
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        return CertificatePublic(
            playlist_title=cert.playlist_title,
            playlist_id=cert.playlist_id,
            recipient_name=cert.recipient_name,
            verification_code=cert.verification_code,
            issued_at=cert.issued_at,
        )

    async def list_for_user(self, user_id: UUID) -> list[CertificateRead]:
        certs = await self.cert_repo.list_for_user(user_id)
        return [CertificateRead.model_validate(c) for c in certs]


def get_cert_repo(session: AsyncSession = Depends(get_session)):
    return CertificateRepository(session)


def get_playlist_repo(session: AsyncSession = Depends(get_session)):
    return PlaylistRepository(session)


def get_user_repo(session: AsyncSession = Depends(get_session)):
    return UserRepository(session)


def get_certificate_service(
    cert_repo: CertificateRepository = Depends(get_cert_repo),
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),
    user_repo: UserRepository = Depends(get_user_repo),
) -> CertificateService:
    return CertificateService(cert_repo, playlist_repo, user_repo)


CertificateServiceDep = Annotated[CertificateService, Depends(get_certificate_service)]
