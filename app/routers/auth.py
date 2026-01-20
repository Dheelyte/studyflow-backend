import json
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, status, HTTPException
from fastapi.responses import RedirectResponse

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
from ..services.google_auth import GoogleRawLoginFlowServiceDep, GoogleUserServiceDep
from ..services.github_auth import GithubRawLoginFlowServiceDep, GithubUserServiceDep
from ..services.apple_auth import AppleRawLoginFlowServiceDep, AppleUserServiceDep
from ..config import settings
from ..services.auth import AuthTokenServiceDep
from ..services.email import EmailService

router = APIRouter(
    prefix="/auth", tags=["Authentication"], dependencies=[Depends(db_session)]
)


@router.post("/register", response_model=MsgResponse, status_code=201)
async def register(
    response: Response,
    user_data: UserCreate,
    user_service: UserServiceDep,
    token_service: AuthTokenServiceDep,
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
    user = await user_service.register_user(user_data)

    access_token = token_service.create_access_token(data={"sub": user.email})
    refresh_token = token_service.create_refresh_token(data={"sub": user.email})
    
    token_service.set_auth_cookies(response, access_token, refresh_token)

    await EmailService.send_welcome_email(user)

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

    await auth_token_service.refresh_user_token(request, response)

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


@router.get("/login/google")
async def login_google(
    google_service: GoogleRawLoginFlowServiceDep
):
    """Initiates the Google OAuth flow."""
    auth_url, state = google_service.get_authorization_url()
    
    response = RedirectResponse(url=auth_url)
    
    # SECURITY FIX: Store state in an HTTPOnly cookie to verify later
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.COOKIE_SECURE, # OAuth state cookie must be Secure for SameSite=None
        samesite=settings.COOKIE_SAMESITE, # Allow cross-site usage for the callback handshake
        max_age=300, # 5 minutes expiration is enough
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    
    return response

@router.get("/callback/google")
async def callback_google(
    request: Request,
    google_service: GoogleRawLoginFlowServiceDep,
    google_user_service: GoogleUserServiceDep,
    auth_token_service: AuthTokenServiceDep,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    # 1. Handle User Cancellation
    redirect_url = f"{settings.FRONTEND_REDIRECT_URL}?login_success=false"
    error_response = RedirectResponse(url=redirect_url)
    
    if error:
        print("DEBUG: Google permission denied: ", error)
        return error_response

    cookie_state = request.cookies.get("oauth_state")
    if not state:
        print("DEBUG: Missing state parameter in callback.")
        return error_response
    if not cookie_state:
        print("DEBUG: Missing oauth_state cookie. Cookie may have been blocked or stripped.")
        return error_response
    if state != cookie_state:
        print("DEBUG: State mismatch. Potential CSRF attack.")
        return error_response

    if not code:
        print("DEBUG: No code received from Google")
        return error_response

    # 3. Exchange code for tokens
    try:
        google_tokens = await google_service.get_tokens(code=code)
    except Exception as e:
        print("DEBUG: Failed to authenticate with Google.")
        return error_response

    # 4. Get User Info & Database Logic
    user_info = await google_service.get_user_info(google_tokens)
    email = user_info.get("email")
    
    # 5. Get/Create User (Scalable: logic is delegated to service)
    user, created = await google_user_service.get_or_create_google_user(email, user_info)
    
    # 6. Issue Tokens & Redirect
    access_token = auth_token_service.create_access_token(data={"sub": user.email})
    refresh_token = auth_token_service.create_refresh_token(data={"sub": user.email})
    
    # Determine redirect URL (could be dynamic based on user role)
    redirect_url = f"{settings.FRONTEND_REDIRECT_URL}?login_success=true"
    response = RedirectResponse(url=redirect_url)
    
    # Set secure cookies
    auth_token_service.set_auth_cookies(response, access_token, refresh_token)
    
    # Cleanup state cookie
    response.delete_cookie("oauth_state")

    # Send welcome email if new user
    if created:
        await EmailService.send_welcome_email(user)
    
    return response


@router.get("/login/github")
async def login_github(
    github_service: GithubRawLoginFlowServiceDep
):
    """Initiates the Github OAuth flow."""
    auth_url, state = github_service.get_authorization_url()
    
    response = RedirectResponse(url=auth_url)
    
    # Store state in cookie for CSRF protection
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.COOKIE_SECURE, 
        samesite=settings.COOKIE_SAMESITE,
        max_age=300,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    
    return response

@router.get("/callback/github")
async def callback_github(
    request: Request,
    github_service: GithubRawLoginFlowServiceDep,
    github_user_service: GithubUserServiceDep,
    auth_token_service: AuthTokenServiceDep,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    # 1. Handle User Cancellation
    redirect_url = f"{settings.FRONTEND_REDIRECT_URL}?login_success=false"
    error_response = RedirectResponse(url=redirect_url)

    # 1. Handle User Cancellation
    if error:
        print("DEBUG: Github permission denied: ", error)
        return error_response

    # 2. Verify State (CSRF Protection)
    cookie_state = request.cookies.get("oauth_state")
    
    # DEBUG LOGGING
    print(f"DEBUG: Github Callback - State Param: {state}, Cookie State: {cookie_state}")
    print(f"DEBUG: All Cookies: {request.cookies.keys()}")

    if not state:
        print("DEBUG: Missing state parameter in callback.")
        return error_response
    if not cookie_state:
        print("DEBUG: Missing oauth_state cookie. Cookie may have been blocked or stripped.")
        return error_response
    if state != cookie_state:
        print("DEBUG: State mismatch. Potential CSRF attack.")
        return error_response

    if not code:
        print("DEBUG: No code received from Github")
        return error_response

    # 3. Exchange code for tokens
    try:
        github_tokens = await github_service.get_tokens(code=code)
    except Exception as e:
        print("DEBUG: Failed to authenticate with Github.")
        return error_response

    # 4. Get User Info
    user_info = await github_service.get_user_info(github_tokens)
    email = user_info.get("email")
    
    # 5. Get/Create User
    user, created = await github_user_service.get_or_create_github_user(email, user_info)

    # 6. Issue Tokens & Redirect
    access_token = auth_token_service.create_access_token(data={"sub": user.email})
    refresh_token = auth_token_service.create_refresh_token(data={"sub": user.email})
    
    # Redirect with success flag
    redirect_url = f"{settings.FRONTEND_REDIRECT_URL}?login_success=true"
    response = RedirectResponse(url=redirect_url)
    
    # Set secure cookies
    auth_token_service.set_auth_cookies(response, access_token, refresh_token)
    
    # Cleanup state cookie
    response.delete_cookie("oauth_state")

    # Send welcome email if new user
    if created:
        await EmailService.send_welcome_email(user)
    
    return response


@router.get("/login/apple")
async def login_apple(
    apple_service: AppleRawLoginFlowServiceDep
):
    """Initiates the Apple Sign In flow."""
    auth_url, state = apple_service.get_authorization_url()
    
    response = RedirectResponse(url=auth_url)
    
    # Store state in cookie for CSRF protection
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=300,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    
    return response

@router.post("/callback/apple")
async def callback_apple(
    request: Request,
    response: Response,
    apple_service: AppleRawLoginFlowServiceDep,
    apple_user_service: AppleUserServiceDep,
    auth_token_service: AuthTokenServiceDep,
):
    """
    Apple Identity Provider Callback.
    Apple sends 'code', 'state' and optionally 'user' as form fields in a POST request.
    """
    
    form_data = await request.form()
    code = form_data.get("code")
    state = form_data.get("state")
    user_json = form_data.get("user") # Only present on first login
    error = form_data.get("error")

    # 1. Handle User Cancellation / Errors
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Apple permission denied: {error}"
        )

    # 2. Verify State (CSRF Protection)
    cookie_state = request.cookies.get("oauth_state")
    
    # DEBUG LOGGING
    print(f"DEBUG: Apple Callback - State Param: {state}, Cookie State: {cookie_state}")
    print(f"DEBUG: All Cookies: {request.cookies.keys()}")

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Missing state parameter in callback."
        )
    if not cookie_state:
        # Note: In a real Form Post, we can't easily query cookies if samesite is strict.
        # Ensure samesite='lax' or 'none' for this to work.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Missing oauth_state cookie. Cookie may have been blocked or stripped."
        )
    if state != cookie_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="State mismatch. Potential CSRF attack."
        )

    if not code:
        raise HTTPException(status_code=400, detail="No code received from Apple")

    # 3. Exchange code for tokens
    try:
        apple_tokens = await apple_service.get_tokens(code=code)
    except Exception as e:
        # Log error
        raise HTTPException(status_code=400, detail="Failed to authenticate with Apple.")

    # 4. Verify ID Token & Get User Info
    # Apple ID token contains email
    claims = apple_service.verify_id_token(apple_tokens.id_token)
    email = claims.get("email")
    
    if not email:
         raise HTTPException(status_code=400, detail="Email not found in Apple ID Token")

    # 5. Get/Create User
    # Parse user_json if available (first login only)
    user_name_data = None
    if user_json:
        try:
            user_name_data = json.loads(user_json)
        except:
            pass
            
    user, created = await apple_user_service.get_or_create_apple_user(email, user_name_data)

    # 6. Issue Tokens & Redirect
    access_token = auth_token_service.create_access_token(data={"sub": user.email})
    refresh_token = auth_token_service.create_refresh_token(data={"sub": user.email})
    
    # Redirect with success flag
    redirect_url = f"{settings.FRONTEND_URL}/dashboard?login_success=true"
    
    # Since this is a POST request from Apple, we must return a 302 Found or 303 See Other
    # to redirect the user's browser to our frontend.
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    
    # Set secure cookies
    auth_token_service.set_auth_cookies(response, access_token, refresh_token)
    
    # Cleanup state cookie
    response.delete_cookie("oauth_state")

    # Send welcome email if new user
    if created:
        await EmailService.send_welcome_email(user)
    
    return response
