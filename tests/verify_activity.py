
import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone, date
from uuid import uuid4

# Add project root to path
sys.path.append(os.getcwd())

from app.db.session import async_session_factory
from app.models.user import User
from app.models.resource import Resource
from app.models.activity import UserDailyActivity
from app.repositories.playlist import PlaylistRepository, ModuleRepository, LessonRepository, ResourceRepository
from app.repositories.user import UserRepository
from app.repositories.activity import ActivityRepository
from app.services.playlist import PlaylistService

async def verify_activity():
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        resource_repo = ResourceRepository(session)
        playlist_repo = PlaylistRepository(session)
        module_repo = ModuleRepository(session)
        lesson_repo = LessonRepository(session)
        activity_repo = ActivityRepository(session)
        
        service = PlaylistService(playlist_repo, module_repo, lesson_repo, resource_repo, user_repo, activity_repo)
        
        # Mock repositories to isolate activity logic
        original_get_resource = resource_repo.get_resource_by_id
        original_get_progress = resource_repo.get_resource_progress
        original_add_progress = resource_repo.add
        
        async def mock_get_resource(id):
            return Resource(id=id, title="Mock", url="url", type="article", description="desc", order=1, lesson_id=1)
            
        async def mock_get_progress(uid, rid):
            return None
            
        async def mock_add_progress(progress):
            pass
            
        resource_repo.get_resource_by_id = mock_get_resource
        resource_repo.get_resource_progress = mock_get_progress
        resource_repo.add = mock_add_progress 
        
        print("Creating test user for activity tracking...")
        user_id = uuid4()
        user = User(
            id=user_id,
            email=f"test_activity_{user_id}@example.com",
            password_hash="hash",
            first_name="Test",
            last_name="User",
            last_active_date=None
        )
        await user_repo.add(user)
        await session.commit()
        
        print("Simulating first resource completion (Today)...")
        await service.mark_resource_completed(101, user_id)
        
        # Check activity
        today_date = datetime.now(timezone.utc).date()
        activities = await activity_repo.get_user_activities(user_id)
        print(f"Activities found: {len(activities)}")
        
        if len(activities) == 1 and activities[0].date == today_date and activities[0].activity_count == 1:
            print("SUCCESS: Initial activity created.")
        else:
             print(f"FAILURE: Expected 1 activity with count 1, got {activities}")
             
        print("Simulating second resource completion (Today)...")
        # For this to work with 'mark_resource_completed', the resource ID must be different 
        # OR we need to simulate that previous progress wasn't completed (which our mock does by returning None)
        await service.mark_resource_completed(102, user_id)
        
        activities = await activity_repo.get_user_activities(user_id)
        current_activity = activities[0]
        print(f"Activity count: {current_activity.activity_count}")
        
        if current_activity.activity_count == 2:
            print("SUCCESS: Activity count incremented.")
        else:
            print(f"FAILURE: Expected count 2, got {current_activity.activity_count}")

        # Note: Testing strictly 'different day' logic is harder with current implementation using datetime.now() inside service.
        # We verified the logic in code, and the unique constraint ensures safety.
        # We can simulate manual insertion for another day for API testing if needed.

if __name__ == "__main__":
    asyncio.run(verify_activity())
