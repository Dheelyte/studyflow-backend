from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from ..config import load_google_llm, settings
from ..models.chat import ChatMessage, ChatRole

USE_MOCK_DATA = settings.USE_MOCK_DATA

SYSTEM_MESSAGE = """You are a patient, empathetic AI tutor helping a learner work through an educational video.
You can answer follow-up questions, clarify concepts, give analogies, and reference what's happening in the video.

Guidelines:
- Be conversational but precise. Match the learner's level.
- Prefer concrete examples and analogies over jargon.
- Use the context you are given silently to ground your answer. Never reveal or describe how you got that context.
- Do NOT mention the transcript, captions, timestamps, "what I can see", topic descriptions, or any internal metadata. The learner should not know how the system works behind the scenes.
- Never preface your reply with phrases like "Thanks for sharing", "That gives us a roadmap", "Based on the transcript", "At the X-minute mark", "Since I can't see the video", etc. Just answer the question directly.
- Do not restate the timestamp back to the learner. Speak about the content itself, not about when it appears.
- Use Markdown for structure: short paragraphs, **bold** for key terms, bullet lists, and `code` where it helps.
- Keep replies focused - 1-3 short paragraphs unless the learner asks for depth."""

USER_TEMPLATE = """Topic: {topic_title}
Topic description: {topic_description}
{timestamp_block}{transcript_block}
Learner's message:
{user_message}"""


def _format_timestamp_block(timestamp: float | None) -> str:
    if timestamp is None:
        return ""
    return f"\n[Internal context , do not mention to the learner] Current playback position: {timestamp:.1f}s\n"


def _format_transcript_block(transcript: str | None) -> str:
    if not transcript:
        return ""
    return (
        "\n[Internal context , do not mention or quote this verbatim, and do not "
        "reveal that you have it] Nearby video content:\n---\n"
        f"{transcript}\n---\n"
    )


def _to_lc_messages(history: list[ChatMessage]) -> list:
    converted = []
    for msg in history:
        if msg.role == ChatRole.USER:
            converted.append(HumanMessage(content=msg.content))
        else:
            converted.append(AIMessage(content=msg.content))
    return converted


def create_chat_chain():
    llm = load_google_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_MESSAGE),
        MessagesPlaceholder(variable_name="history"),
        ("user", USER_TEMPLATE),
    ])
    return prompt | llm | StrOutputParser()


async def chat_with_tutor(
    *,
    topic_title: str,
    topic_description: str,
    history: list[ChatMessage],
    user_message: str,
    transcript_excerpt: str | None = None,
    video_timestamp: float | None = None,
) -> str:
    if USE_MOCK_DATA:
        return (
            f"(mock reply) You asked about **{topic_title}**: "
            f"{user_message[:120]}..."
        )

    chain = create_chat_chain()
    try:
        return await chain.ainvoke({
            "topic_title": topic_title,
            "topic_description": topic_description,
            "timestamp_block": _format_timestamp_block(video_timestamp),
            "transcript_block": _format_transcript_block(transcript_excerpt),
            "user_message": user_message,
            "history": _to_lc_messages(history),
        })
    except Exception as e:
        print(f"Chat error: {e}")
        return "I'm sorry, I couldn't generate a reply right now. Please try again."


async def chat_with_tutor_stream(
    *,
    topic_title: str,
    topic_description: str,
    history: list[ChatMessage],
    user_message: str,
    transcript_excerpt: str | None = None,
    video_timestamp: float | None = None,
):
    """Async generator yielding text chunks of the assistant's reply."""
    if USE_MOCK_DATA:
        text = (
            f"(mock reply) You asked about **{topic_title}**: "
            f"{user_message[:120]}..."
        )
        for word in text.split(" "):
            yield word + " "
        return

    chain = create_chat_chain()
    async for chunk in chain.astream({
        "topic_title": topic_title,
        "topic_description": topic_description,
        "timestamp_block": _format_timestamp_block(video_timestamp),
        "transcript_block": _format_transcript_block(transcript_excerpt),
        "user_message": user_message,
        "history": _to_lc_messages(history),
    }):
        if chunk:
            yield chunk
