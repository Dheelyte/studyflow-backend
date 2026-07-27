from fastapi import APIRouter, Depends

from ..db.session import db_session
from ..dependencies.auth import AuthUserDep
from ..dependencies.playlist import PlaylistIdDep
from ..schema.certificate import (
    CertificateEligibility,
    CertificatePublic,
    CertificateRead,
)
from ..services.certificate import CertificateServiceDep


router = APIRouter(tags=["Certificates"], dependencies=[Depends(db_session)])


@router.get(
    "/playlists/{playlist_ref}/certificate",
    response_model=CertificateEligibility,
)
async def get_playlist_certificate_status(
    playlist_id: PlaylistIdDep,
    auth_user: AuthUserDep,
    service: CertificateServiceDep,
):
    return await service.get_eligibility(auth_user.id, playlist_id)


@router.post(
    "/playlists/{playlist_ref}/certificate",
    response_model=CertificateRead,
)
async def issue_playlist_certificate(
    playlist_id: PlaylistIdDep,
    auth_user: AuthUserDep,
    service: CertificateServiceDep,
):
    return await service.issue_certificate(auth_user.id, playlist_id)


@router.get("/me/certificates", response_model=list[CertificateRead])
async def list_my_certificates(
    auth_user: AuthUserDep,
    service: CertificateServiceDep,
):
    return await service.list_for_user(auth_user.id)


# Public verification — no auth required so external recipients can verify.
public_router = APIRouter(tags=["Certificates"], dependencies=[Depends(db_session)])


@public_router.get("/certificates/{code}", response_model=CertificatePublic)
async def verify_certificate(code: str, service: CertificateServiceDep):
    return await service.get_by_code_public(code)
