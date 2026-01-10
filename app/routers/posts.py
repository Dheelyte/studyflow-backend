from fastapi import APIRouter, Depends, status
from typing import List

from ..dependencies.auth import AuthUserDep, OptionalAuthUserDep
from ..db.session import db_session
from ..schema.post import PostCreate, PostResponse, PostUpdate
from ..services.post import PostServiceDep

router = APIRouter(prefix="/posts", tags=["posts"], dependencies=[Depends(db_session)])

@router.post("", response_model=PostResponse, status_code=201)
async def create_post(
    post: PostCreate, 
    auth_user: AuthUserDep,
    post_service: PostServiceDep
):
    return await post_service.create_post(post, auth_user.id)


@router.get("/feed", response_model=List[PostResponse])
async def get_user_feed(
    post_service: PostServiceDep,
    auth_user: AuthUserDep,
    skip: int = 0, 
    limit: int = 10
):
    return await post_service.get_user_feed(auth_user.id, skip, limit)


@router.get("/{community_id}/posts", response_model=List[PostResponse])
async def list_community_posts(
    community_id: int,
    auth_user: OptionalAuthUserDep,
    post_service: PostServiceDep,
    skip: int = 0, 
    limit: int = 10
):
    user_id = auth_user.id if auth_user else None
    return await post_service.list_community_posts(community_id, skip, limit, user_id)


@router.get("/explore", response_model=List[PostResponse])
async def get_explore_feed(
    post_service: PostServiceDep,
    skip: int = 0, 
    limit: int = 100
):
    """
    Public explore feed: returns latest posts from all communities.
    """
    return await post_service.get_explore_feed(skip, limit)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int, 
    post_service: PostServiceDep
):
    return await post_service.get_post(post_id)


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int, 
    post_update: PostUpdate, 
    post_service: PostServiceDep
):
    return await post_service.update_post(post_id, post_update)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int, 
    post_service: PostServiceDep
):
    await post_service.delete_post(post_id)
    return None


@router.post("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_post(
    post_id: int, 
    auth_user: AuthUserDep,
    post_service: PostServiceDep
):
    await post_service.like_post(post_id, auth_user.id)
    return None


@router.delete("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_post(
    post_id: int, 
    auth_user: AuthUserDep,
    post_service: PostServiceDep
):
    await post_service.unlike_post(post_id, auth_user.id)
    return None
