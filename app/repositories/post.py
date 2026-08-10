from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select
from sqlalchemy.orm import joinedload

from app.models.like import Like

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
        result = await self.session.execute(
            select(Post).options(joinedload(Post.user)).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()
        if post and post.user:
            setattr(post, "user_name", f"{post.user.first_name} {post.user.last_name}")
        return post
    
    async def get_feed_for_user(self, user_id: int, skip: int, limit: int) -> list[Post]:
        comments_count_sub = (
            select(func.count(Comment.id))
            .where(Comment.post_id == Post.id)
            .scalar_subquery()
        )
        
        stmt = (
            select(Post, comments_count_sub.label("comments_count"))
            .options(joinedload(Post.user), joinedload(Post.community))
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
            if post.user:
                setattr(post, "user_name", f"{post.user.first_name} {post.user.last_name}")
            if post.community:
                setattr(post, "community_name", post.community.name)
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
            .options(joinedload(Post.user), joinedload(Post.community))
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        posts = []
        for row in result:
            post = row[0]
            setattr(post, "comments_count", row[1] or 0)
            if post.user:
                setattr(post, "user_name", f"{post.user.first_name} {post.user.last_name}")
            if post.community:
                setattr(post, "community_name", post.community.name)
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
            .options(joinedload(Post.user))
            .where(Post.community_id == community_id)
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        posts = []
        for row in result:
            post = row[0]
            setattr(post, "comments_count", row[1] or 0)
            if post.user:
                setattr(post, "user_name", f"{post.user.first_name} {post.user.last_name}")
            posts.append(post)
        return posts
    
    async def update(self, post: Post) -> Post:
        self.session.add(post)
        await self.session.flush()
        return post
    
    async def delete(self, post: Post):
        await self.session.delete(post)
        await self.session.flush()

    async def check_like_exists(self, post_id: int, user_id: UUID):
        query = select(Like).where(Like.user_id == user_id, Like.post_id == post_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def like_post(self, like: Like) -> Like:
        self.session.add(like)
        await self.session.flush()
        return like

    async def unlike_post(self, post_id: int, user_id: UUID):
        query = delete(Like).where(Like.user_id == user_id, Like.post_id == post_id)
        await self.session.execute(query)
    
    async def fill_like_info(self, posts: list[Post], user_id: int = None):
        """
        Efficiently populates likes_count and liked_by_user for a list of posts.
        Directly attaching attributes to the SQLAlchemy models for Pydantic serialization.
        """
        if not posts:
            return
        post_ids = [p.id for p in posts]
        
        # 1. Get like counts
        stmt_counts = (
            select(Like.post_id, func.count(Like.id))
            .where(Like.post_id.in_(post_ids))
            .group_by(Like.post_id)
        )
        counts_res = await self.session.execute(stmt_counts)
        counts_map = dict(counts_res.all())
        
        # 2. Get user liked status if user_id is provided
        liked_map = {}
        if user_id:
            stmt_liked = (
                select(Like.post_id)
                .where(Like.post_id.in_(post_ids), Like.user_id == user_id)
            )
            liked_res = await self.session.execute(stmt_liked)
            liked_map = {row[0]: True for row in liked_res.all()}
        # 3. Populate
        for p in posts:
            p.likes_count = counts_map.get(p.id, 0)
            p.liked_by_user = liked_map.get(p.id, False)
