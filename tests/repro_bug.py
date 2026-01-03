import asyncio
import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory
from app.repositories.playlist import PlaylistRepository, ModuleRepository, ResourceRepository, LessonRepository
from app.repositories.user import UserRepository
from app.services.playlist import PlaylistService
from app.models.user import User
from app.models.playlist import Playlist, PlaylistLevel
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.resource import Resource
from app.models.progress import UserResourceProgress, UserPlaylist, UserModuleProgress
from app.services.activity import ActivityService
from app.repositories.activity import ActivityRepository
from app.repositories.streak import StreakRepository

from sqlalchemy import text

async def main():
    async with async_session_factory() as session:
        # Repositories
        playlist_repo = PlaylistRepository(session)
        module_repo = ModuleRepository(session)
        lesson_repo = LessonRepository(session)
        resource_repo = ResourceRepository(session)
        user_repo = UserRepository(session)
        activity_repo = ActivityRepository(session)
        streak_repo = StreakRepository(session)
        
        # Service
        activity_service = ActivityService(activity_repo)
        playlist_service = PlaylistService(
            playlist_repo, module_repo, lesson_repo, resource_repo, 
            user_repo, activity_repo, streak_repo, activity_service
        )
        async def mock_update_daily(*args): pass
        activity_service.update_daily_activity = mock_update_daily

        # 1. Create User
        user = await user_repo.get_by_email("bug_repro@example.com")
        if not user:
            user = User(
                email="bug_repro@example.com", 
                first_name="Bug", 
                last_name="Repro", 
                password_hash="dummy_hash"
            )
            session.add(user)
            await session.flush()
            print(f"Created user: {user.id}")

        # 2. Create Playlist with 1 Module
        playlist = Playlist(
            title="Bug Repro Playlist",
            level=PlaylistLevel.BEGINNER,
            timeline="1 week",
            description="Testing bug",
            objectives=["Test"],
            user_id=user.id
        )
        await playlist_repo.add(playlist)
        print(f"Created playlist: {playlist.id}")

        # Module 1
        m1 = Module(title="M1", description="D", order=1, playlist_id=playlist.id)
        await module_repo.add(m1)
        l1 = Lesson(title="L1", estimated_time="1h", module_id=m1.id, order=1)
        await lesson_repo.add(l1)
        r1 = Resource(title="R1", url="u", type="t", description="d", order=1, lesson_id=l1.id)
        await resource_repo.add(r1)
        
        # 4. Create UserPlaylist
        up = UserPlaylist(user_id=user.id, playlist_id=playlist.id)
        session.add(up)
        await session.flush()

        # 5. Mark R1 as completed via Service (Should trigger module completion)
        print("Marking R1 as completed...")
        await playlist_service.mark_resource_completed(r1.id, user.id)
        
        # 6. Verify UserModuleProgress exists
        print("Checking DB for UserModuleProgress...")
        ump_result = await session.execute(
            text("SELECT * FROM user_module_progress WHERE user_id = :uid AND module_id = :mid"),
            {"uid": str(user.id), "mid": m1.id}
        )
        ump = ump_result.one_or_none()
        print(f"UserModuleProgress: {ump}")

        # 7. Fetch User Playlists via Service
        print("\n--- Fetching User Playlists ---")
        param_playlists = await playlist_service.get_user_playlists(user.id)
        for p in param_playlists:
            if p.playlist.id == playlist.id:
                print(f"Playlist ID: {p.playlist.id}")
                print(f"  Total Modules: {p.progress.total_modules}")
                print(f"  Completed Modules: {p.progress.completed_modules}")
                
        # Cleanup
        await session.rollback()
        print("\nRolled back changes.")

if __name__ == "__main__":
    asyncio.run(main())
