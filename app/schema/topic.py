from pydantic import BaseModel, ConfigDict


class TopicRead(BaseModel):
    id: int
    title: str
    description: str
    order: int
    youtube_video_id: str | None = None
    is_completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class TopicVideoResponse(BaseModel):
    topic_id: int
    youtube_video_id: str
    title: str = ""
    description: str = ""
    is_completed: bool = False


class TopicExplainRequest(BaseModel):
    video_id: str
    timestamp: float


class TopicExplainResponse(BaseModel):
    explanation: str
    transcript_excerpt: str | None = None
