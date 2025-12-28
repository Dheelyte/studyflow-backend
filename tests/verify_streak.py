
import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Add project root to path
sys.path.append(os.getcwd())

from app.db.session import async_session_factory
from app.models.user import User
from app.models.resource import Resource
from app.models.progress import UserResourceProgress
from app.repositories.playlist import PlaylistRepository, ModuleRepository, LessonRepository, ResourceRepository
from app.repositories.user import UserRepository
from app.services.playlist import PlaylistService

async def verify_streak():
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        resource_repo = ResourceRepository(session)
        playlist_repo = PlaylistRepository(session) # Not used directly but needed for service init
        module_repo = ModuleRepository(session)
        lesson_repo = LessonRepository(session)
        
        service = PlaylistService(playlist_repo, module_repo, lesson_repo, resource_repo, user_repo)
        
        # Create a dummy resource
        resource = Resource(title="Test Resource", url="http://test.com", type="article", description="desc", order=1, lesson_id=1) # lesson_id constraint might fail if lesson doesn't exist.
        # We might need to create a resource properly or mock get_resource_by_id
        # Let's mock get_resource_by_id to return a dummy object if we can, or just insert one.
        # Inserting linked objects is tedious.
        
        # Let's mock the repositories for easier testing of logic
        # Actually, let's just insert a user and check the logic part, mocking the resource part.
        
        print("Creating test user...")
        user_id = uuid4()
        user = User(
            id=user_id,
            email=f"test_streak_{user_id}@example.com",
            password_hash="hash",
            first_name="Test",
            last_name="User",
            current_streak=1,
            longest_streak=1,
            last_active_date=datetime.now(timezone.utc) - timedelta(days=1) # Yesterday
        )
        await user_repo.add(user)
        await session.commit()
        
        print(f"User created with streak 1, last active yesterday: {user.last_active_date}")
        
        # Mocking resource repo's get_resource_by_id and get_resource_progress
        # Because we don't want to set up full hierarchy of Playlist->Module->Lesson->Resource
        
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
        resource_repo.add = mock_add_progress # We don't care about progress record persistence for this test, only User
        
        print("Simulating resource completion (Today)...")
        await service.mark_resource_completed(123, user_id)
        
        # Refresh user from DB
        updated_user = await user_repo.get_by_id(user_id)
        print(f"Updated User Streak: {updated_user.current_streak}")
        print(f"Updated User Last Active: {updated_user.last_active_date}")
        
        if updated_user.current_streak == 2:
            print("SUCCESS: Streak incremented correctly.")
        else:
            print("FAILURE: Streak did not increment.")
            
        # Test Broken Streak
        print("\nTesting Broken Streak...")
        user_broken_id = uuid4()
        user_broken = User(
            id=user_broken_id,
            email=f"test_broken_{user_broken_id}@example.com",
            password_hash="hash",
            first_name="Test",
            last_name="User",
            current_streak=5,
            longest_streak=5,
            last_active_date=datetime.now(timezone.utc) - timedelta(days=2) # 2 days ago
        )
        await user_repo.add(user_broken)
        await session.commit()
        
        await service.mark_resource_completed(123, user_broken_id)
        updated_user_broken = await user_repo.get_by_id(user_broken_id)
        
        print(f"Broken User Streak: {updated_user_broken.current_streak}")
        if updated_user_broken.current_streak == 1:
             print("SUCCESS: Streak reset correctly.")
        else:
             print("FAILURE: Streak did not reset.")

if __name__ == "__main__":
    asyncio.run(verify_streak())
