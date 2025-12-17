from fastapi import APIRouter, Depends, HTTPException, status

from ..db.session import db_session
from ..dependencies.auth import AuthUserDep
from ..schema.base import DataResponse, MsgResponse
from ..schema.user import PasswordChangeData, UserRead
from ..services.auth import Hasher
from ..services.user import UserServiceDep

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(db_session)])


@router.get("/me", response_model=DataResponse[UserRead])
async def get_current_user_info(auth_user: AuthUserDep):
    """
    Retrieve the authenticated user's profile information.

    This endpoint returns the details of the currently authenticated user based
    on the access token provided in the request. It is typically used to populate
    profile pages or verify that the user is logged in.

    **Flow:**
    1. Extract user identity from the access token.
    2. Ensure the user is active and authenticated.
    3. Return the user's serialized data.

    **Returns:**
    - The authenticated user's information (`UserRead`).
    """

    return DataResponse(data=auth_user)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    response_model=MsgResponse,
)
async def change_password(
    password_data: PasswordChangeData, auth_user: AuthUserDep, user_service: UserServiceDep
):
    """
    Change the password for the currently authenticated user.

    This endpoint allows a logged-in user to update their password by providing
    their current (old) password and a new password. The old password is verified
    before allowing the update for security purposes.

    **Flow:**
    1. Verify that the old password matches the user's current password.
    2. Validate and hash the new password.
    3. Update the user's password in the database.

    **Error Responses:**
    - `400 Bad Request` — Old password does not match.

    **Returns:**
    - A success message confirming the password has been updated.
    """

    await user_service.update_password(
        auth_user, password_data.old_password, password_data.new_password
    )

    return MsgResponse(message="Password updated successfully")
