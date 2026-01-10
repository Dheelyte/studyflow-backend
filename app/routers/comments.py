from fastapi import APIRouter, Depends, status
from typing import List

from ..dependencies.auth import AuthUserDep
from ..db.session import db_session
from ..schema.comment import CommentCreate, CommentResponse, CommentUpdate
from ..services.comment import CommentServiceDep


router = APIRouter(prefix="/comments", tags=["comments"], dependencies=[Depends(db_session)])

@router.post("", response_model=CommentResponse, status_code=201)
async def create_comment(
    comment: CommentCreate, 
    auth_user: AuthUserDep,
    comment_service: CommentServiceDep
):
    return await comment_service.create_comment(comment, auth_user.id)


@router.get("/post/{post_id}", response_model=List[CommentResponse])
async def list_post_comments(
    post_id: int, 
    comment_service: CommentServiceDep,
    skip: int = 0, 
    limit: int = 10
):
    return await comment_service.list_post_comments(post_id, skip, limit)


@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int, 
    comment_update: CommentUpdate, 
    comment_service: CommentServiceDep
):
    return await comment_service.update_comment(comment_id, comment_update)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int, 
    comment_service: CommentServiceDep
):
    await comment_service.delete_comment(comment_id)
    return None
