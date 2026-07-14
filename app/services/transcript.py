import asyncio
from youtube_transcript_api import YouTubeTranscriptApi


class TranscriptService:
    async def get_transcript_window(
        self, video_id: str, timestamp: float, before: float = 30.0, after: float = 15.0
    ) -> str:
        """Fetch transcript and extract text around the given timestamp.

        Args:
            video_id: YouTube video ID
            timestamp: Current playback position in seconds
            before: Seconds of context before the timestamp
            after: Seconds of context after the timestamp

        Returns:
            Concatenated transcript text for the time window
        """
        loop = asyncio.get_event_loop()
        api = YouTubeTranscriptApi()
        fetched = await loop.run_in_executor(None, lambda: api.fetch(video_id))

        window_start = max(0, timestamp - before)
        window_end = timestamp + after

        segments = [
            snippet.text
            for snippet in fetched
            if snippet.start >= window_start and snippet.start <= window_end
        ]

        return " ".join(segments)
