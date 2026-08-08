import json
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ..config import load_google_llm
from ..schema.resource import Curriculum
from ..config import settings

USE_MOCK_DATA = settings.USE_MOCK_DATA


def create_generate_curriculum_chain():
    llm = load_google_llm()
    parser = PydanticOutputParser(pydantic_object=Curriculum)
    format_instructions = parser.get_format_instructions()

    system_message = """You are an expert Instructional Designer and Subject Matter Expert. Your task is to design a high-quality, structured learning roadmap for a learner."""

    user_template = """### Role
    You are an expert Instructional Designer and Subject Matter Expert. Your task is to design a high-quality, structured learning roadmap for a learner who wants to learn the following:
    - Topic: {topic}{customization}

    ### Audience Context
    Primerly's learners are primarily people building tech and digital skills - software development, data, design, cloud, cybersecurity, digital marketing. When the topic is technical, emphasize hands-on practice, tooling, and project-based progression. Still produce a high-quality roadmap for any topic you are given.

    ### Constraints & Quality Standards
    1. Scalability: Organize the roadmap into logical 'Modules' and 'Lessons'.
    2. Topic Design: Each lesson must contain a list of 'Topics'. Each topic is a focused learning unit with a 'title' and 'description'. The title should be specific enough to find a relevant educational YouTube video for it. The description should explain what the learner will understand after studying it.
    3. Pedagogical Flow: Ensure a progression from foundational concepts to practical application. Start with the basics and build up to more advanced concepts.
    4. Formatting: Output the response EXCLUSIVELY in valid JSON format.

    ### Naming Constraints for 'curriculum_title'
    - Must be a concise 'Short-Form' title (max 4 words).
    - PROHIBITED: Do not include subtitles, colons, or catchphrases.
    - GOOD: "React.js", "Python Programming", "Data Analysis", "UI/UX Design", "DevOps"
    - BAD: "React Foundations", "Python Programming: A Complete Guide to Hooks"

    ### Output Schema
    The JSON must follow this structure:

    {format_instructions}

    Respond ONLY with valid JSON."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_template)
    ])

    prompt = prompt.partial(format_instructions=format_instructions)
    chain = prompt | llm | parser

    return chain


async def generate_curriculum_response(
    topic: str,
    duration_weeks: int | None = None,
    level: str | None = None,
):
    if USE_MOCK_DATA:
        return load_mock_curriculum()

    customization_lines = []
    if duration_weeks:
        customization_lines.append(
            f"- Target duration: about {duration_weeks} week{'s' if duration_weeks != 1 else ''}. "
            "Scale the number of modules and lessons so the roadmap is realistically completable in that time."
        )
    if level:
        customization_lines.append(
            f"- Learner's starting level: {level}. Pitch the depth, prerequisites, and pacing accordingly."
        )
    customization = ("\n    " + "\n    ".join(customization_lines)) if customization_lines else ""

    chain = create_generate_curriculum_chain()
    try:
        result = await chain.ainvoke({
            "topic": topic,
            "customization": customization,
        })
        return result
    except Exception as e:
        print(f"Analysis error: {e}")
        return Curriculum(
            curriculum_title="",
            overview="",
            learning_objectives=[],
            modules=[]
        )

def load_mock_curriculum() -> Curriculum:
    """
    Helper function to load the local JSON file for testing.
    Uses pathlib to ensure it works across different operating systems.
    """
    try:
        base_dir = Path.cwd()
        file_path = base_dir / "tests" / "curriculum.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Mock file not found at: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Curriculum.model_validate(data)

    except Exception as e:
        print(f"Mock Data Error: {e}")
        raise e
