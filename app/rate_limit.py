from slowapi import Limiter
from slowapi.util import get_remote_address

# Lives in its own module so routers (e.g. the Paystack webhook's @limiter.exempt)
# can import it without a circular import through app.main.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
