import json
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ..config import load_google_llm, settings
from ..schema.project import ProjectBrief

USE_MOCK_DATA = settings.USE_MOCK_DATA

CAPSTONE_REQUIREMENT_RANGE = "6 to 10"
PRACTICE_REQUIREMENT_RANGE = "3 to 5"


def create_generate_project_chain():
    llm = load_google_llm()
    parser = PydanticOutputParser(pydantic_object=ProjectBrief)
    format_instructions = parser.get_format_instructions()

    system_message = """You are an experienced engineering mentor who sets practical build tasks. You design projects that force a learner to apply what they just studied, not to recite it."""

    user_template = """### Task
    Design one hands-on project brief for a learner on the course below.

    - Course: {course_title}
    - Scope: {scope_label}
    - What the learner has just covered: {covered_topics}

    ### Audience Context
    Primerly's learners are building tech and digital skills - software development, data, design, cloud, security, digital marketing. The project must be something they can actually produce and show to someone: an app, a script, a dashboard, a design file, a campaign plan, an edited video. Match the deliverable to the subject matter rather than assuming code.

    ### Requirements for your output
    1. Scope: this is a {scope_word}. Produce {requirement_range} requirements.
    2. Each requirement must be concrete and objectively checkable by the learner - something they can look at and say done or not done. No vague requirements like "understand X" or "write good code".
    3. The brief should explain what to build and why it matters, then give a suggested approach. Do not give a step-by-step solution or paste in finished code - the learner must do the work.
    4. Assume no paid tools or services are required.
    5. estimated_time should be realistic for someone new to the topic.
    6. The summary is shown publicly to people deciding whether to take the course, so make it appealing and specific.

    ### Output Schema
    {format_instructions}

    Respond ONLY with valid JSON."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_template)
    ])

    prompt = prompt.partial(format_instructions=format_instructions)
    return prompt | llm | parser


async def generate_project_response(
    course_title: str,
    covered_topics: list[str],
    is_capstone: bool,
    module_title: str | None = None,
) -> ProjectBrief | None:
    if USE_MOCK_DATA:
        return load_mock_project(is_capstone)

    if is_capstone:
        scope_label = f"final capstone for the whole course '{course_title}'"
        scope_word = "substantial capstone project"
        requirement_range = CAPSTONE_REQUIREMENT_RANGE
    else:
        scope_label = f"practice build for the module '{module_title}'"
        scope_word = "focused practice build"
        requirement_range = PRACTICE_REQUIREMENT_RANGE

    chain = create_generate_project_chain()
    try:
        return await chain.ainvoke({
            "course_title": course_title,
            "scope_label": scope_label,
            "scope_word": scope_word,
            "requirement_range": requirement_range,
            "covered_topics": ", ".join(covered_topics) or course_title,
        })
    except Exception as e:
        print(f"Project generation error: {e}")
        return None


def load_mock_project(is_capstone: bool) -> ProjectBrief:
    """Mirrors the curriculum/quiz mock path so USE_MOCK_DATA works end to end."""
    file_path = Path.cwd() / "tests" / ("project_capstone.json" if is_capstone else "project_practice.json")
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return ProjectBrief.model_validate(json.load(f))

    # Fall back to a built-in stub so mock mode never hard-fails on a missing fixture.
    count = 6 if is_capstone else 3
    return ProjectBrief(
        title="Sample Project" if not is_capstone else "Sample Capstone",
        summary="A stand-in project used when USE_MOCK_DATA is enabled.",
        brief="This is mock project content. Set USE_MOCK_DATA=false to generate real briefs.",
        estimated_time="4 hours",
        requirements=[
            {"id": i + 1, "text": f"Mock requirement {i + 1}"} for i in range(count)
        ],
    )
