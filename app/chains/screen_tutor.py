from langchain_core.messages import HumanMessage, SystemMessage

from ..config import load_google_llm, settings
from ..schema.screen_tutor import AnswerStyle

USE_MOCK_DATA = settings.USE_MOCK_DATA

_SHARED_RULES = """You are looking at a screenshot of a learner's own screen. They are part way through a tech course and are stuck on something.

Guidelines:
- Ground your answer in what is actually visible in the screenshot. Refer to what you can see plainly - the file, the error, the line - but do not narrate the whole screen back to them.
- If the screenshot does not contain enough to answer, say what you would need to see rather than guessing.
- Use the course context you are given to pitch your answer at their level and connect it to what they have been studying. Do not read the context back to them.
- Ignore anything on screen that is unrelated to their question, and never comment on personal content that happens to be visible.
- Use Markdown: short paragraphs, **bold** for key terms, and fenced code blocks for code.
- Keep it tight - a few short paragraphs at most."""

SYSTEM_HINT = f"""{_SHARED_RULES}

The learner asked for a HINT, not the answer. Point them at the specific place the problem is and give them the idea they are missing, so they can make the fix themselves. Do not write the corrected code for them. End by telling them they can ask again for the full answer."""

SYSTEM_DIRECT = f"""{_SHARED_RULES}

The learner asked to be told directly. Give them the answer and the corrected code where relevant, then explain briefly why it was wrong so the fix sticks."""


def _split_data_url(data_url: str) -> tuple[str, str]:
    """('audio/wav', '<base64>') from 'data:audio/wav;base64,<base64>'."""
    header, _, encoded = data_url.partition(",")
    mime_type = header.removeprefix("data:").split(";")[0] or "audio/wav"
    return mime_type, encoded


def _context_block(context: dict) -> str:
    """Course context the model should use silently."""
    lines = []
    if context.get("course_title"):
        lines.append(f"Course: {context['course_title']}")
    if context.get("module_title"):
        lines.append(f"Module: {context['module_title']}")
    if context.get("topic_title"):
        lines.append(f"Currently studying: {context['topic_title']}")
    if context.get("topic_description"):
        lines.append(f"Which covers: {context['topic_description']}")
    if context.get("project_title"):
        lines.append(f"Building the project: {context['project_title']}")
    if context.get("project_summary"):
        lines.append(f"Project goal: {context['project_summary']}")

    if not lines:
        return ""
    body = "\n".join(lines)
    return f"[Internal context - use it silently, never repeat it back]\n{body}\n\n"


async def screen_tutor_stream(
    *,
    image_data_url: str,
    question: str,
    answer_style: AnswerStyle,
    context: dict,
    region_data_url: str | None = None,
    audio_data_url: str | None = None,
):
    """Stream an answer about what is on the learner's screen.

    When the learner highlights part of the screen, the crop is sent alongside the
    full frame so the model knows which of several visible panes actually matters.
    """
    if USE_MOCK_DATA:
        for part in ["Looking at your screen, ", "the issue is on the highlighted line. ",
                     "(mock screen tutor response)"]:
            yield part
        return

    llm = load_google_llm()
    system = SYSTEM_HINT if answer_style == AnswerStyle.HINT else SYSTEM_DIRECT

    if audio_data_url:
        text_part = (
            f"{_context_block(context)}The learner asked their question out loud - "
            "it is in the attached audio. Answer the question they actually asked."
        )
    else:
        asked = question.strip() or "I'm stuck on what's on my screen. What's going wrong?"
        text_part = f"{_context_block(context)}Learner's question:\n{asked}"

    content = [
        {"type": "text", "text": text_part},
        {"type": "text", "text": "Full screen:"},
        {"type": "image_url", "image_url": image_data_url},
    ]

    if audio_data_url:
        mime_type, encoded = _split_data_url(audio_data_url)
        # source_type "base64" is the form the integration actually base64-decodes;
        # the "media" part type would pass the string through as raw bytes.
        content.append({
            "type": "file",
            "source_type": "base64",
            "mime_type": mime_type,
            "data": encoded,
        })

    if region_data_url:
        content.append({
            "type": "text",
            "text": (
                "The learner highlighted this specific area and it is almost certainly "
                "what they are asking about. Focus your answer here, using the full "
                "screen only for surrounding context."
            ),
        })
        content.append({"type": "image_url", "image_url": region_data_url})

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=content),
    ]

    async for chunk in llm.astream(messages):
        text = getattr(chunk, "content", "")
        if isinstance(text, list):
            # Gemini can return content as a list of parts.
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        if text:
            yield text
