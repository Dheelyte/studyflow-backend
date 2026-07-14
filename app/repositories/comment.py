from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..models.comment import Comment


def _attach_user_name(comment: Comment) -> Comment:
    if comment and comment.user:
        setattr(
            comment,
            "user_name",
            f"{comment.user.first_name} {comment.user.last_name}".strip(),
        )
    return comment


class CommentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, comment: Comment) -> Comment:
        self.session.add(comment)
        await self.session.flush()
        return comment

    async def get_by_id(self, comment_id: int) -> Comment | None:
        result = await self.session.execute(
            select(Comment)
            .options(joinedload(Comment.user))
            .where(Comment.id == comment_id)
        )
        comment = result.scalar_one_or_none()
        return _attach_user_name(comment) if comment else None

    async def get_by_post(self, post_id: int, skip: int, limit: int) -> list[Comment]:
        result = await self.session.execute(
            select(Comment)
            .options(joinedload(Comment.user))
            .where(Comment.post_id == post_id)
            .order_by(Comment.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        comments = result.scalars().all()
        for c in comments:
            _attach_user_name(c)
        return comments
    
    async def update(self, comment: Comment) -> Comment:
        self.session.add(comment)
        await self.session.flush()
        return comment
    
    async def delete(self, comment: Comment):
        await self.session.delete(comment)
        await self.session.flush()
