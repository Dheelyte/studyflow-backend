from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import ChatRole


class ChatMessageRead(BaseModel):
    id: int
    role: ChatRole
    content: str
    video_timestamp: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    session_id: int
    topic_id: int
    messages: list[ChatMessageRead]
    has_more: bool = False


class ChatMessagesPage(BaseModel):
    messages: list[ChatMessageRead]
    has_more: bool


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    video_timestamp: float | None = None


class SendMessageResponse(BaseModel):
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead


class TranscribeRequest(BaseModel):
    # Spoken question as a data URL (data:audio/wav;base64,...). Forwarded to the
    # model and dropped , the recording is never persisted.
    audio: str = Field(min_length=32)


class TranscribeResponse(BaseModel):
    text: str
