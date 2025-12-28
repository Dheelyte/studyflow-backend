from datetime import date
from pydantic import BaseModel

class UserActivity(BaseModel):
    date: date
    activity_count: int
    
class UserActivityResponse(BaseModel):
    activities: list[UserActivity]
