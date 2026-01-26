from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status, Depends
from ..db.session import get_session
from ..models.waitlist import Waitlist
from ..schema.waitlist import WaitlistCreate
from fastapi import HTTPException

class WaitlistService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def join_waitlist(self, waitlist_data: WaitlistCreate):
        # Check if email already exists
        query = select(Waitlist).where(Waitlist.email == waitlist_data.email)
        result = await self.db_session.execute(query)
        existing_entry = result.scalar_one_or_none()

        if existing_entry:
            # We fail silently or return a message saying it's already there. 
            # For privacy/UX, commonly we just say "You're on the list!" or return HTTP 409.
            # Let's return a specific validation error or just success if idempotent.
            # The plan said "handle gracefully". Let's raise 409 for now so frontend handles it, 
            # or just return success if we want to be idempotent. 
            # Given it's a "join" action, idempotency is nice. 
            # But let's stick to explicit behaviour for now: 
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already on the waitlist"
            )

        new_entry = Waitlist(email=waitlist_data.email)
        self.db_session.add(new_entry)
        
        return new_entry

def get_waitlist_service(session: AsyncSession = Depends(get_session)) -> WaitlistService:
    return WaitlistService(session)

WaitlistServiceDep = Annotated[WaitlistService, Depends(get_waitlist_service)]
