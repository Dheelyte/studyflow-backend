from .base import BadRequestError


class UserExistsError(BadRequestError):
    """Raised when attempting to create a user that already exists."""
    pass


class InactiveUserError(BadRequestError):
    """Raised when attempting to create a user that already exists."""
    pass