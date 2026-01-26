from fastapi import APIRouter, Depends

from ..schema.waitlist import WaitlistCreate, WaitlistResponse
from ..services.waitlist import WaitlistServiceDep
from ..db.session import db_session

router = APIRouter(
    prefix="/waitlist", tags=["Waitlist"], dependencies=[Depends(db_session)]
)

@router.post("", response_model=WaitlistResponse, status_code=201)
async def join_waitlist(
    waitlist_data: WaitlistCreate,
    waitlist_service: WaitlistServiceDep,
):
    """
    Join variables waitlist.
    """
    await waitlist_service.join_waitlist(waitlist_data)
    
    return WaitlistResponse(message="You're on the list!")
