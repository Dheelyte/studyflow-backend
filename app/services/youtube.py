import httpx
from ..config import settings

# Well-known educational video IDs used as mock fallbacks (topic → video_id)
MOCK_VIDEO_IDS = [
    "dQw4w9WgXcQ",  # placeholder - replace with real IDs in prod
    "rfscVS0vtbw",
    "ZyhVh-qy4gg",
    "HXV3zeQKqGY",
    "b9eMGE7QtTk",
]


class YouTubeService:
    BASE_URL = "https://www.googleapis.com/youtube/v3/search"

    async def search_video(self, query: str) -> str | None:
        """Search YouTube for the best educational video. Returns video_id or None."""
        if settings.USE_MOCK_DATA or not settings.YOUTUBE_API_KEY:
            # Return a deterministic mock video ID based on the query
            idx = abs(hash(query)) % len(MOCK_VIDEO_IDS)
            return MOCK_VIDEO_IDS[idx]

        print("=================== NOT MOCK DATA (1) ==================")

        params = {
            "part": "snippet",
            "q": f"{query} tutorial educational",
            "type": "video",
            "maxResults": 1,
            "order": "relevance",
            "videoDuration": "medium",
            "key": settings.YOUTUBE_API_KEY,
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            print("=================== NOT MOCK DATA (2) ==================")
            if items:
                return items[0]["id"]["videoId"]
            return None
