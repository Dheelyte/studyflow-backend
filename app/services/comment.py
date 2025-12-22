from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from ..repositories.comment import CommentRepository
from ..repositories.post import PostRepository
from ..repositories.user import UserRepository
from ..schema.comment import CommentCreate, CommentUpdate
from ..models.comment import Comment
from ..exceptions.base import NotFoundError
from ..db.session import get_session
from ..services.post import get_post_repo
from ..services.user import get_user_repo


class CommentService:
    def __init__(
        self, 
        comment_repo: CommentRepository, 
        post_repo: PostRepository,
        user_repo: UserRepository
    ):
        self.comment_repo = comment_repo
        self.post_repo = post_repo
        self.user_repo = user_repo

    async def create_comment(self, comment_data: CommentCreate, user_id: int) -> Comment:
        post = await self.post_repo.get_by_id(comment_data.post_id)
        if not post:
            raise NotFoundError("Post not found")
            
        new_comment = Comment(
            content=comment_data.content,
            post_id=comment_data.post_id,
            user_id=user_id
        )
        return await self.comment_repo.create(new_comment)
    
    async def get_comment(self, comment_id: int) -> Comment:
        comment = await self.comment_repo.get_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")
        return comment
    
    async def list_post_comments(self, post_id: int, skip: int, limit: int) -> list[Comment]:
        return await self.comment_repo.get_by_post(post_id, skip, limit)
    
    async def update_comment(self, comment_id: int, update_data: CommentUpdate) -> Comment:
        comment = await self.get_comment(comment_id)
        if update_data.content is not None:
            comment.content = update_data.content
        return await self.comment_repo.update(comment)
    
    async def delete_comment(self, comment_id: int):
        comment = await self.get_comment(comment_id)
        await self.comment_repo.delete(comment)


def get_comment_repo(session: AsyncSession = Depends(get_session)) -> CommentRepository:
    return CommentRepository(session)

def get_comment_service(
    comment_repo: CommentRepository = Depends(get_comment_repo),
    post_repo: PostRepository = Depends(get_post_repo),
    user_repo: UserRepository = Depends(get_user_repo)
) -> CommentService:
    return CommentService(comment_repo, post_repo, user_repo)


CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]
