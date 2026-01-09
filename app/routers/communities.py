from fastapi import APIRouter, Depends, status
from typing import List

from ..db.session import db_session
from ..schema.community import CommunityCreate, CommunityResponse, CommunityUpdate, CommunityDetailResponse
from ..services.community import CommunityServiceDep
from ..dependencies.auth import AuthUserDep, OptionalAuthUserDep

router = APIRouter(
    prefix="/communities", tags=["communities"], dependencies=[Depends(db_session)]
)

@router.post("", response_model=CommunityResponse)
async def create_community(
    community: CommunityCreate, 
    community_service: CommunityServiceDep,
    auth_user: AuthUserDep 
):
    return await community_service.create_community(community, auth_user.id)


@router.get("/", response_model=List[CommunityResponse])
async def list_communities(
    community_service: CommunityServiceDep,
    skip: int = 0, 
    limit: int = 100
):
    return await community_service.list_communities(skip, limit)


@router.get("/my-communities", response_model=List[CommunityDetailResponse])
async def list_my_communities(
    community_service: CommunityServiceDep,
    auth_user: AuthUserDep
):
    return await community_service.get_my_communities(auth_user.id)


@router.get("/explore", response_model=List[CommunityResponse])
async def list_explore_communities(
    community_service: CommunityServiceDep,
    auth_user: AuthUserDep
):
    return await community_service.get_explore_communities(auth_user.id)


@router.get("/{community_id}", response_model=CommunityDetailResponse)
async def get_community(
    community_id: int, 
    community_service: CommunityServiceDep,
    auth_user: OptionalAuthUserDep
):
    user_id = auth_user.id if auth_user else None
    return await community_service.get_community(community_id, user_id)


@router.put("/{community_id}", response_model=CommunityDetailResponse)
async def update_community(
    community_id: int,
    auth_user: AuthUserDep,
    community_update: CommunityUpdate, 
    community_service: CommunityServiceDep,
):
    # Service update returns updated object. 
    # Logic in service for update needs to ensure member_count/is_member fields are present 
    # if we want to return CommunityDetailResponse.
    # Currently service update sets member_count=0 placeholder.
    return await community_service.update_community(
        community_id, auth_user.id, community_update
    )


@router.delete("/{community_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_community(
    community_id: int,
    auth_user: AuthUserDep,
    community_service: CommunityServiceDep
):
    await community_service.delete_community(community_id, auth_user.id)
    return None


@router.post("/{community_id}/join")
async def join_community(
    community_id: int, 
    auth_user: AuthUserDep,
    community_service: CommunityServiceDep
):
    await community_service.join_community(community_id, auth_user.id)
    return {"message": "Joined successfully"}


@router.post("/{community_id}/leave")
async def leave_community(
    community_id: int,
    auth_user: AuthUserDep,
    community_service: CommunityServiceDep
):
    await community_service.leave_community(community_id, auth_user.id)
    return {"message": "Left successfully"}
