from .base import BadRequestError, UnauthorizedError


class LoginError(BadRequestError):
    """Raised when attempting to create a user that already exists."""
    pass

class LoginError(UnauthorizedError):
    """Raised when attempting to create a user that already exists."""
    pass