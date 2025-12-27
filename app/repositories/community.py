from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, case, exc
from ..models.community import Community, community_members


class CommunityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, community: Community) -> Community:
        self.session.add(community)
        await self.session.flush()
        await self.session.refresh(community)
        return community
    
    async def get_by_id(self, community_id: int) -> Community | None:
        result = await self.session.execute(select(Community).where(Community.id == community_id))
        return result.scalar_one_or_none()
    
    async def get_with_member_info(self, community_id: int, user_id: int | None = None) -> dict | None:
        # Subquery for member count
        member_count_sub = (
            select(func.count(community_members.c.user_id))
            .where(community_members.c.community_id == Community.id)
            .scalar_subquery()
        )
        
        # Check if specific user is member
        # Only query if user_id is provided
        is_member_sub = False
        if user_id:
             is_member_sub = (
                select(1)
                .where(
                    (community_members.c.community_id == Community.id) & 
                    (community_members.c.user_id == user_id)
                )
                .exists()
             )
        stmt = select(Community, member_count_sub.label("member_count")).where(Community.id == community_id)
        if user_id:
            stmt = stmt.add_columns(is_member_sub.label("is_member"))
        result = await self.session.execute(stmt)
        row = result.first()
        if not row:
            return None
            
        community = row[0]
        count = row[1]
        is_member = row[2] if user_id and len(row) > 2 else False
        
        setattr(community, "member_count", count)
        setattr(community, "is_member", is_member)
        return community
    
    async def get_all(self, skip: int, limit: int) -> list[Community]:
        result = await self.session.execute(select(Community).offset(skip).limit(limit))
        return result.scalars().all()
    
    async def update(self, community: Community) -> Community:
        self.session.add(community)
        await self.session.flush()
        await self.session.refresh(community)
        return community
    
    async def delete(self, community: Community):
        await self.session.delete(community)
        await self.session.flush()
    
    async def is_member(self, user_id: int, community_id: int) -> bool:
        stmt = select(community_members).where(
            (community_members.c.user_id == user_id) & 
            (community_members.c.community_id == community_id)
        )
        result = await self.session.execute(stmt)
        return result.first() is not None
    
    async def add_member(self, user_id: int, community_id: int):
        # try:
        await self.session.execute(community_members.insert().values(user_id=user_id, community_id=community_id))
        await self.session.flush()
        # except exc.IntegrityError:
        #     await self.session.rollback()
    
    async def remove_member(self, user_id: int, community_id: int):
        stmt = community_members.delete().where(
            (community_members.c.user_id == user_id) & 
            (community_members.c.community_id == community_id)
        )
        await self.session.execute(stmt)
        await self.session.flush()
    
    async def get_joined_by_user(self, user_id: int) -> list[Community]:
        # Alias specifically needed here because outer query ALSO joins community_members
        cm_count_alias = community_members.alias()
        
        member_count_sub = (
            select(func.count(cm_count_alias.c.user_id))
            .where(cm_count_alias.c.community_id == Community.id)
            .scalar_subquery()
        )
        stmt = (
            select(Community, member_count_sub.label("member_count"))
            .join(community_members, Community.id == community_members.c.community_id)
            .where(community_members.c.user_id == user_id)
        )
        
        result = await self.session.execute(stmt)
        communities = []
        for row in result:
            comm = row[0]
            count = row[1]
            setattr(comm, "member_count", count)
            setattr(comm, "is_member", True)
            communities.append(comm)
        return communities
    
    async def get_explore_for_user(self, user_id: int) -> list[Community]:
        # Get communities user has NOT joined.
        # EXCLUDING member count as requested.
        
        joined_ids = (
            select(community_members.c.community_id)
            .where(community_members.c.user_id == user_id)
            .scalar_subquery()
        )
        
        stmt = (
            select(Community)
            .where(Community.id.notin_(joined_ids))
        )
        
        result = await self.session.execute(stmt)
        communities = result.scalars().all()
        for comm in communities:
            # We don't set member_count here. Pydantic schema CommunityResponse won't have it either.
            setattr(comm, "is_member", False)
        return communities
