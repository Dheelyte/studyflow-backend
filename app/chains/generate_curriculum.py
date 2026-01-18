import json
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ..config import load_google_llm
from ..schema.resource import Resource, Curriculum
from ..config import settings

USE_MOCK_DATA = settings.USE_MOCK_DATA


def create_generate_curriculum_chain():
    llm = load_google_llm()
    parser = PydanticOutputParser(pydantic_object=Curriculum)
    format_instructions = parser.get_format_instructions()

    system_message = """You are an expert Instructional Designer and Subject Matter Expert. Your task is to design a high-quality, structured curriculum for a learner."""

    user_template = """### Role
    You are an expert Instructional Designer and Subject Matter Expert. Your task is to design a high-quality, structured curriculum for a learner based on the following parameters:
    - Topic: {topic}
    - Experience Level: {experience_level} (e.g., Beginner, Intermediate, Advanced)
    - Duration: {duration} (e.g., 4 weeks, 10 hours)

    ### Constraints & Quality Standards
    1. Scalability: Organize the curriculum into logical 'Modules' and 'Lessons'. For the curriculum title, don't 
    2. Resource Integrity: Provide placeholders for external resources. Each resource must include a 'Type' (Video, Article, Interactive), a 'Description' of why it is useful, and a 'Search_Query' that the user can use to find the best current version on the web (this avoids the issue of broken links/hallucinated URLs). The links should not lead to a paid course (e.g. Coursera, Udemy, etc).
    3. Pedagogical Flow: Ensure a progression from foundational concepts to practical application.
    4. Formatting: Output the response EXCLUSIVELY in valid JSON format.

    ### Naming Constraints for 'curriculum_title'
    - Must be a concise 'Short-Form' title (max 4 words).
    - PROHIBITED: Do not include subtitles, colons, or catchphrases.
    - GOOD: "React.js", "Python Programming", "Data Analysis"
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


async def generate_curriculum_response(topic: str, experience_level: str, duration: str):
    if USE_MOCK_DATA:
        return load_mock_curriculum()
    
    chain = create_generate_curriculum_chain()
    try:
        result = chain.ainvoke({
            "topic": topic,
            "experience_level": experience_level,
            "duration": duration,
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
        # Construct path relative to where the app is running
        # Adjust 'tests' folder location if your structure differs
        base_dir = Path.cwd()
        file_path = base_dir / "tests" / "curriculum.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Mock file not found at: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Validate that the JSON actually matches your Pydantic model
        # using .model_validate() (Pydantic v2) or .parse_obj() (Pydantic v1)
        return Curriculum.model_validate(data)
        
    except Exception as e:
        print(f"Mock Data Error: {e}")
        # Re-raise or handle gracefully depending on preference
        raise e