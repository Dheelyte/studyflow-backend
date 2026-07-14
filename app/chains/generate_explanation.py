from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..config import load_google_llm, settings

USE_MOCK_DATA = settings.USE_MOCK_DATA


def create_explanation_chain():
    llm = load_google_llm()

    system_message = """You are a patient, empathetic AI tutor. A learner is watching an educational video
and has paused because they don't understand something. You have access to the transcript
around the moment they paused.

Your job is to:
1. Identify what concept is being discussed at that point in the video
2. Explain it in simple, beginner-friendly language
3. Use analogies or real-world examples where helpful
4. Keep your explanation concise but thorough (2-4 paragraphs)
5. If the transcript context is unclear, use the topic title to guide your explanation"""

    user_template = """The learner is studying: {topic_title}

They paused the video at {timestamp} seconds. Here is the transcript around that moment:
---
{transcript_excerpt}
---

Please explain what's being discussed at this point in a clear, beginner-friendly way."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_template)
    ])

    chain = prompt | llm | StrOutputParser()
    return chain


async def generate_explanation(topic_title: str, transcript_excerpt: str, timestamp: float) -> str:
    if USE_MOCK_DATA:
        return f"This section of the video about '{topic_title}' is explaining a key concept. Let me break it down for you in simpler terms..."

    chain = create_explanation_chain()
    try:
        result = await chain.ainvoke({
            "topic_title": topic_title,
            "transcript_excerpt": transcript_excerpt,
            "timestamp": str(timestamp),
        })
        return result
    except Exception as e:
        print(f"Explanation error: {e}")
        return "I'm sorry, I couldn't generate an explanation at this time. Please try again."
