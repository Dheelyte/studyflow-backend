from contextvars import ContextVar
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

# This holds the session specific to the current asyncio task (request)
session_context: ContextVar[Optional[AsyncSession]] = ContextVar(
    "session_context", default=None
)


def get_session() -> AsyncSession:
    """Helper to retrieve the session from context or raise error if missing."""
    session = session_context.get()
    if session is None:
        raise RuntimeError("No database session found in context.")
    return session


async def db_session():
    """
    Dependency that:
    1. Creates a session.
    2. Sets it in the global ContextVar (so helpers can find it).
    3. Commits on success, Rolls back on error.
    4. Cleans up the ContextVar.
    """
    async with async_session_factory() as session:
        # 1. Set the session in the context var
        token = session_context.set(session)

        try:
            # 2. Yield control to the route
            # We yield the session so the route *can* use it if it wants,
            # but services will use get_session() internally.
            yield session

            # 3. Commit if route completes successfully
            await session.commit()

        except HTTPException as http_ex:
            # Rollback on HTTP errors (e.g. 404, 400)
            await session.rollback()
            raise http_ex

        except Exception as e:
            # Rollback on code crashes
            await session.rollback()
            raise e

        finally:
            # 4. CRITICAL: Reset the context var to avoid leaking memory/state
            session_context.reset(token)
            await session.close()
