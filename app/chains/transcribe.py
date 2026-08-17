from langchain_core.messages import HumanMessage, SystemMessage

from ..config import load_google_llm, settings

USE_MOCK_DATA = settings.USE_MOCK_DATA

SYSTEM = """You transcribe short spoken questions from learners on a tech-learning platform.

Rules:
- Return only the transcription, with no preamble, quotes, or commentary.
- Transcribe what was said verbatim; do not answer the question, summarise it, or add anything.
- Punctuate and capitalise normally, and spell technical terms the way they are written in the field ("React", "SQL", "async/await").
- If the audio has no intelligible speech, return an empty string."""


def _split_data_url(data_url: str) -> tuple[str, str]:
    """('audio/wav', '<base64>') from 'data:audio/wav;base64,<base64>'."""
    header, _, encoded = data_url.partition(",")
    mime_type = header.removeprefix("data:").split(";")[0] or "audio/wav"
    return mime_type, encoded


async def transcribe_audio(audio_data_url: str) -> str:
    """Spoken question -> text, for typing into a chat composer."""
    if USE_MOCK_DATA:
        return "How does this actually work?"

    mime_type, encoded = _split_data_url(audio_data_url)
    llm = load_google_llm()

    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=[
            {"type": "text", "text": "Transcribe this recording."},
            # source_type "base64" is the form the integration actually base64-decodes;
            # the "media" part type would pass the string through as raw bytes.
            {
                "type": "file",
                "source_type": "base64",
                "mime_type": mime_type,
                "data": encoded,
            },
        ]),
    ]

    response = await llm.ainvoke(messages)
    text = response.content
    if isinstance(text, list):
        # Some providers return content parts rather than a plain string.
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    return (text or "").strip()
