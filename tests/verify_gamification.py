
import asyncio
import sys
import os
from datetime import datetime, timezone
from uuid import uuid4
from math import floor, sqrt
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from app.db.session import async_session_factory
from app.models.user import User
from app.schema.user import UserRead
from app.models.resource import Resource
from app.repositories.playlist import PlaylistRepository, ModuleRepository, LessonRepository, ResourceRepository
from app.repositories.user import UserRepository
from app.repositories.activity import ActivityRepository
from app.repositories.streak import StreakRepository
from app.services.playlist import PlaylistService
from app.services.activity import ActivityService

async def verify_gamification():
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        resource_repo = ResourceRepository(session)
        playlist_repo = PlaylistRepository(session)
        module_repo = ModuleRepository(session)
        lesson_repo = LessonRepository(session)
        activity_repo = ActivityRepository(session)
        streak_repo = StreakRepository(session)
        activity_service = ActivityService(activity_repo)
        
        service = PlaylistService(
            playlist_repo, module_repo, lesson_repo, resource_repo, 
            user_repo, activity_repo, streak_repo, activity_service
        )
        
        # Mock repositories
        async def mock_get_resource(id):
            return Resource(id=id, title="Mock", url="url", type="article", description="desc", order=1, lesson_id=1)
        async def mock_get_progress(uid, rid):
            return None
        async def mock_add_progress(progress):
            pass
            
        resource_repo.get_resource_by_id = mock_get_resource
        resource_repo.get_resource_progress = mock_get_progress
        resource_repo.add = mock_add_progress
        
        print("Creating test user for gamification...")
        user_id = uuid4()
        user = User(
            id=user_id,
            email=f"test_xp_{user_id}@example.com",
            password_hash="hash",
            first_name="XP",
            last_name="Tester",
            last_active_date=None,
            total_xp=0,
            current_streak=0
        )
        await user_repo.add(user)
        await session.commit()
        
        # Test Case 1: Base XP (Streak 0)
        print("Test 1: Completing resource with 0 streak...")
        await service.mark_resource_completed(201, user_id)
        
        # Refresh user
        result = await session.execute(text(f"SELECT total_xp, current_streak FROM users WHERE id = '{user_id}'"))
        row = result.fetchone()
        xp_1 = row[0]
        streak_1 = row[1] # Should be 1 now because streak logic ran too
        
        print(f"XP after 1st completion: {xp_1} (Expected ~10)")
        
        if xp_1 == 10:
             print("SUCCESS: Base XP correct.")
        else:
             print(f"FAILURE: Expected 10, got {xp_1}")

        # Test Case 2: Multiplier XP (Streak is now 1)
        # Multiplier = 1 + (1 * 0.1) = 1.1
        # Expected XP = 10 * 1.1 = 11
        print("Test 2: Completing resource with streak 1...")
        await service.mark_resource_completed(202, user_id)
        
        result = await session.execute(text(f"SELECT total_xp FROM users WHERE id = '{user_id}'"))
        xp_2 = result.scalar()
        gained = xp_2 - xp_1
        
        print(f"XP after 2nd completion: {xp_2} (Gained {gained}, Expected 11)")
        
        if gained == 11:
            print("SUCCESS: Multiplier XP correct.")
        else:
            print(f"FAILURE: Expected 11, got {gained}")

        # Test Case 3: Level Calculation
        # Let's manually set XP to 400 (Level 2 threshold: 0.1 * sqrt(400) = 0.1 * 20 = 2)
        user.total_xp = 400
        user_schema = UserRead.model_validate(user)
        print(f"Level for 400 XP: {user_schema.level} (Expected 2)")
        
        if user_schema.level == 2:
            print("SUCCESS: Level 2 correct.")
        else:
             print(f"FAILURE: Expected 2, got {user_schema.level}")

        user.total_xp = 399
        user_schema = UserRead.model_validate(user)
        print(f"Level for 399 XP: {user_schema.level} (Expected 1)")
        if user_schema.level == 1:
            print("SUCCESS: Level 1 correct.")
        
        print(f"Level Name for Level 1: {user_schema.level_name} (Expected 'Novice Explorer')")
        if user_schema.level_name == "Novice Explorer":
            print("SUCCESS: Level Name correct.")

        # Test Case 4: Higher Level Name
        user.total_xp = 10000 # Level 10 (0.1 * 100 = 10)
        user_schema = UserRead.model_validate(user)
        print(f"Level for 10000 XP: {user_schema.level}")
        print(f"Level Name: {user_schema.level_name} (Expected 'Knowledge Seeker')")
        
        if user_schema.level == 10 and user_schema.level_name == "Knowledge Seeker":
            print("SUCCESS: High Level Name correct.")

if __name__ == "__main__":
    asyncio.run(verify_gamification())
