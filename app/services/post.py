from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from ..repositories.post import PostRepository
from ..repositories.community import CommunityRepository
from ..repositories.user import UserRepository
from ..schema.post import PostCreate, PostUpdate
from ..models.post import Post
from ..exceptions.base import NotFoundError
from ..db.session import get_session
from ..services.community import get_community_repo
from ..services.user import get_user_repo


class PostService:
    def __init__(
        self, 
        post_repo: PostRepository, 
        community_repo: CommunityRepository,
        user_repo: UserRepository
    ):
        self.post_repo = post_repo
        self.community_repo = community_repo
        self.user_repo = user_repo

    async def create_post(self, post_data: PostCreate, user_id: int) -> Post:
        community = await self.community_repo.get_by_id(post_data.community_id)
        if not community:
            raise NotFoundError("Community not found")
        
        # User validation implicitly via FK or check
        # user = await self.user_repo.get_by_id(user_id) # Optional check
        
        new_post = Post(
            content=post_data.content,
            community_id=post_data.community_id,
            user_id=user_id
        )
        return await self.post_repo.create(new_post)
    
    async def get_post(self, post_id: int) -> Post:
        post = await self.post_repo.get_by_id(post_id)
        if not post:
            raise NotFoundError("Post not found")
        return post
    
    async def get_user_feed(self, user_id: int, skip: int, limit: int) -> list[Post]:
        return await self.post_repo.get_feed_for_user(user_id, skip, limit)
    
    async def get_explore_feed(self, skip: int, limit: int) -> list[Post]:
        return await self.post_repo.explore_posts(skip, limit)
    
    async def list_community_posts(self, community_id: int, skip: int, limit: int) -> list[Post]:
        return await self.post_repo.get_by_community(community_id, skip, limit)
    
    async def update_post(self, post_id: int, update_data: PostUpdate) -> Post:
        post = await self.get_post(post_id)
        if update_data.title is not None:
            post.title = update_data.title
        if update_data.content is not None:
            post.content = update_data.content
        return await self.post_repo.update(post)
    
    async def delete_post(self, post_id: int):
        post = await self.get_post(post_id)
        await self.post_repo.delete(post)


def get_post_repo(session: AsyncSession = Depends(get_session)) -> PostRepository:
    return PostRepository(session)

def get_post_service(
    post_repo: PostRepository = Depends(get_post_repo),
    community_repo: CommunityRepository = Depends(get_community_repo),
    user_repo: UserRepository = Depends(get_user_repo)
) -> PostService:
    return PostService(post_repo, community_repo, user_repo)


PostServiceDep = Annotated[PostService, Depends(get_post_service)]
