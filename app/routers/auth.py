from fastapi import APIRouter, Depends, Request, Response, status

from ..db.session import db_session
from ..schema.auth import (
    LoginData,
    PasswordResetData,
    PasswordResetCodeCheck,
    PasswordResetRequest,
    PasswordResetVerify,
)
from ..schema.base import MsgResponse
from ..schema.user import UserCreate
from ..services.auth import (
    AuthServiceDep,
    AuthTokenServiceDep,
    PasswordResetServiceDep,
)
from ..services.user import UserServiceDep

router = APIRouter(
    prefix="/auth", tags=["Authentication"], dependencies=[Depends(db_session)]
)


@router.post("/register", response_model=MsgResponse, status_code=201)
async def register(
    user_data: UserCreate,
    user_service: UserServiceDep,
):
    """
    Register a new user account.

    This endpoint creates a new user, generates a verification code, and sends
    a verification email to complete account activation. User creation and
    verification code generation are wrapped inside an atomic database
    transaction to ensure data integrity.

    **Validation Rules:**
    - Password must contain at least 8 characters.
    - Password must include at least one number.

    **Workflow:**
    1. Check if the email is already registered.
    2. Create the user and a corresponding email verification code.
    3. Send the verification email to the user.

    **Returns:**
    - A message confirming that the registration process was successful.

    **Raises:**
    - `HTTPException (400)`: If a user with the given email already exists.
    - Other internal exceptions if user creation or email sending fails.
    """
    await user_service.register_user(user_data)

    return MsgResponse(message="Registration successful")


@router.post("/login", response_model=MsgResponse)
async def login(
    response: Response,
    login_data: LoginData,
    auth_service: AuthServiceDep,
    token_service: AuthTokenServiceDep,
):
    """
    Authenticate a user and generate access/refresh tokens.

    This endpoint validates the user's credentials, ensures the account is active
    and email-verified, and then issues JWT access and refresh tokens. The tokens
    are securely stored in HTTP-only cookies.

    **Authentication Flow:**
    1. Validate the provided email and password.
    2. Ensure the account is active.
    3. Ensure the user's email has been verified.
    4. Generate JWT access and refresh tokens.
    5. Set the tokens as secure cookies on the response.

    **Error Responses:**
    - `401 Unauthorized` — Incorrect credentials.
    - `401 Unauthorized` — Account is inactive.
    - `401 Unauthorized` — Email not verified (includes action hint).

    **Returns:**
    - A success message indicating that login was successful.
    """
    user = await auth_service.authenticate_user(
        login_data.email, login_data.password
    )
    
    access_token = token_service.create_access_token(data={"sub": user.email})
    refresh_token = token_service.create_refresh_token(data={"sub": user.email})
    
    token_service.set_auth_cookies(response, access_token, refresh_token)

    return MsgResponse(message="Login Successful")


@router.post("/refresh", response_model=MsgResponse)
async def refresh_token(
    request: Request,
    response: Response,
    auth_token_service: AuthTokenServiceDep,
):
    """
    Refresh the user's access token using a valid refresh token.

    This endpoint reads the refresh token stored in secure HTTP-only cookies,
    validates it, and issues a new short-lived access token. This allows the user
    to remain logged in without re-entering their credentials.

    **Flow:**
    1. Extract refresh token from cookies.
    2. Validate the refresh token (checks signature + expiry).
    3. Ensure the associated user exists and is active.
    4. Generate a new access token.
    5. Write the new access token back to cookies.

    **Error Responses:**
    - `401 Unauthorized` — Refresh token missing.
    - `401 Unauthorized` — Refresh token is invalid or expired.
    - `401 Unauthorized` — User not found or inactive.

    **Returns:**
    - A success message confirming the access token has been renewed.
    """

    auth_token_service.refresh_user_token(request, response)

    return MsgResponse(message="Token refresh successful")


@router.post(
    "/request-password-reset",
    status_code=status.HTTP_200_OK,
    response_model=MsgResponse,
)
async def request_password_reset(
    request_data: PasswordResetRequest,
    password_reset_service: PasswordResetServiceDep,
):
    """
    Request a password reset for a user.

    This endpoint accepts an email address and, if the user exists, generates a
    password reset code and sends a reset email. For security reasons, the
    response does not reveal whether the email belongs to a registered user,
    preventing account enumeration.

    **Flow:**
    1. Look up the user by email.
    2. If the user exists:
       - Generate a password reset code.
       - Send a reset email containing the code.
    3. Always return a generic success message.

    **Security Note:**
    The same response is returned whether or not the email exists to protect
    against user enumeration attacks.

    **Returns:**
    - A message indicating that a reset email will be sent if the account exists.
    """

    await password_reset_service.request_password_reset(request_data.email)

    return MsgResponse(
        message="If the email exists, a password reset code has been sent"
    )


@router.post(
    "/verify-reset-code",
    status_code=status.HTTP_200_OK,
    response_model=PasswordResetVerify,
)
async def verify_reset_code(
    verify_data: PasswordResetCodeCheck, password_reset_service: PasswordResetServiceDep
):
    """
    Verify a password reset code before allowing the user to proceed.

    This endpoint checks whether the submitted reset code is valid and has not
    expired for the specified email address. It is typically called by the UI
    before showing the "Enter new password" screen, ensuring the token is still
    usable.

    **Flow:**
    1. Extract email and reset code from the request.
    2. Validate the code against the database.
    3. If valid, return a success response.
    4. If invalid or expired, return a `400 Bad Request` error.

    **Returns:**
    - `{ "is_valid": true }` if the reset code is valid.
    - `400 Bad Request` if the reset code is invalid or expired.
    """

    await password_reset_service.verify_reset_code(
        code=verify_data.code, email=verify_data.email
    )
    
    return PasswordResetVerify(is_valid=True)


@router.post("/reset-password", response_model=MsgResponse)
async def reset_password(
    reset_data: PasswordResetData, password_reset_service: PasswordResetServiceDep
):
    """
    Reset a user's password using a valid reset code.

    This endpoint accepts an email, reset code, and new password. It ensures the
    reset token is valid, not expired, and corresponds to the correct user before
    updating the password. It also prevents the user from reusing their old
    password.

    **Flow:**
    1. Validate the email + code combination.
    2. Ensure the reset code is still active and not expired.
    3. Prevent password reuse by checking against the old password hash.
    4. Update the user's password and invalidate the reset token.

    **Error Responses:**
    - `400 Bad Request` — Invalid or expired reset code.
    - `400 Bad Request` — New password matches the old password.

    **Returns:**
    - A success message once the password has been updated.
    """

    await password_reset_service.reset_password_with_token(reset_data)

    return MsgResponse(message="Password reset successfully")


@router.post("/logout", response_model=MsgResponse)
async def logout(response: Response, token_Service: AuthTokenServiceDep):
    token_Service.clear_auth_cookies(response)

    return MsgResponse(message="Logged out")
