from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from ..models.post import Post
from ..models.comment import Comment
from ..models.community import community_members


class PostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, post: Post) -> Post:
        self.session.add(post)
        await self.session.flush()
        # Verify if pydantic response needs explicit setting if defaulting to 0
        setattr(post, "comments_count", 0)
        return post
    
    async def get_by_id(self, post_id: int) -> Post | None:
        result = await self.session.execute(select(Post).where(Post.id == post_id))
        return result.scalar_one_or_none()
    
    async def get_feed_for_user(self, user_id: int, skip: int, limit: int) -> list[Post]:
        comments_count_sub = (
            select(func.count(Comment.id))
            .where(Comment.post_id == Post.id)
            .scalar_subquery()
        )
        
        stmt = (
            select(Post, comments_count_sub.label("comments_count"))
            .join(community_members, Post.community_id == community_members.c.community_id)
            .where(community_members.c.user_id == user_id)
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        
        posts = []
        for row in result:
            post = row[0]
            setattr(post, "comments_count", row[1] or 0)
            posts.append(post)
        return posts
    
    async def explore_posts(self, skip: int, limit: int) -> list[Post]:
        # Return all posts ordered by creation date
        comments_count_sub = (
            select(func.count(Comment.id))
            .where(Comment.post_id == Post.id)
            .scalar_subquery()
        )
        
        result = await self.session.execute(
            select(Post, comments_count_sub.label("comments_count"))
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        posts = []
        for row in result:
            post = row[0]
            setattr(post, "comments_count", row[1] or 0)
            posts.append(post)
        return posts
    
    async def get_by_community(self, community_id: int, skip: int, limit: int) -> list[Post]:
        comments_count_sub = (
            select(func.count(Comment.id))
            .where(Comment.post_id == Post.id)
            .scalar_subquery()
        )
        
        result = await self.session.execute(
            select(Post, comments_count_sub.label("comments_count"))
            .where(Post.community_id == community_id)
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        posts = []
        for row in result:
            post = row[0]
            setattr(post, "comments_count", row[1] or 0)
            posts.append(post)
        return posts
    
    async def update(self, post: Post) -> Post:
        self.session.add(post)
        await self.session.flush()
        return post
    
    async def delete(self, post: Post):
        await self.session.delete(post)
        await self.session.flush()
