from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from ..repositories.community import CommunityRepository
from ..repositories.user import UserRepository
from ..schema.community import CommunityCreate, CommunityUpdate, CommunityResponse
from ..models.community import Community
from ..exceptions.base import NotFoundError, BadRequestError, UnauthorizedError
from ..db.session import get_session
from ..services.user import get_user_repo


class CommunityService:
    def __init__(self, community_repo: CommunityRepository, user_repo: UserRepository):
        self.community_repo = community_repo
        self.user_repo = user_repo

    async def create_community(self, community_data: CommunityCreate, created_by: int) -> Community:
        new_community = Community(
            name=community_data.name,
            description=community_data.description,
            created_by=created_by
        )
        created = await self.community_repo.create(new_community)
        await self.community_repo.add_member(created_by, created.id)
        # Populate ephemeral fields for response
        setattr(created, "member_count", 1)
        setattr(created, "is_member", True)
        return created
    
    async def get_community(self, community_id: int, user_id: int | None = None) -> Community:
        community = await self.community_repo.get_with_member_info(community_id, user_id)
        if not community:
            raise NotFoundError("Community not found")
        return community
    
    async def list_communities(self, skip: int, limit: int) -> list[Community]:
        # Legacy support if needed, or update to use explore defaults?
        # If no user_id, can't calc is_member.
        return await self.community_repo.get_all(skip, limit)
    
    async def get_my_communities(self, user_id: int) -> list[Community]:
        return await self.community_repo.get_joined_by_user(user_id)
    
    async def get_explore_communities(self, user_id: int) -> list[Community]:
        return await self.community_repo.get_explore_for_user(user_id)
    
    async def update_community(
        self, community_id: int, created_by: int, update_data: CommunityUpdate
    ) -> Community:
        # Update doesn't fetch member info usually, but response model expects it?
        # We need to preserve or re-fetch.
        community = await self.community_repo.get_by_id(community_id)
        if not community:
             raise NotFoundError("Community not found")
        if community.created_by != created_by:
            raise UnauthorizedError("You did not create this community")
             
        if update_data.name is not None:
            community.name = update_data.name
        if update_data.description is not None:
            community.description = update_data.description
            
        updated = await self.community_repo.update(community)
        # Re-fetch info or just default (admin usage mostly)
        setattr(updated, "member_count", 0) # Placeholder
        setattr(updated, "is_member", False)
        return updated
    
    async def delete_community(self, community_id: int):
        community = await self.community_repo.get_by_id(community_id)
        if not community:
             raise NotFoundError("Community not found")
        await self.community_repo.delete(community)
    
    async def join_community(self, community_id: int, user_id: int):
        # We can optimize by checking existence via lightweight query or handling error
        if await self.community_repo.is_member(user_id, community_id):
            raise BadRequestError("User already in community")
        
        # Ensure community exists
        if not await self.community_repo.get_by_id(community_id):
             raise NotFoundError("Community not found")
             
        await self.community_repo.add_member(user_id, community_id)
    
    async def leave_community(self, community_id: int, user_id: int):
        if not await self.community_repo.get_by_id(community_id):
             raise NotFoundError("Community not found")
        await self.community_repo.remove_member(user_id, community_id)


def get_community_repo(session: AsyncSession = Depends(get_session)) -> CommunityRepository:
    return CommunityRepository(session)

def get_community_service(
    community_repo: CommunityRepository = Depends(get_community_repo),
    user_repo: UserRepository = Depends(get_user_repo)
) -> CommunityService:
    return CommunityService(community_repo, user_repo)

CommunityServiceDep = Annotated[CommunityService, Depends(get_community_service)]
