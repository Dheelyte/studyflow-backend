import json
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ..config import settings, load_google_llm
from ..schema.quiz import QuizBase

USE_MOCK_DATA = settings.USE_MOCK_DATA


def create_generate_quiz_chain():
    llm = load_google_llm()
    parser = PydanticOutputParser(pydantic_object=QuizBase)
    format_instructions = parser.get_format_instructions()

    system_message = """### SYSTEM ROLE & OBJECTIVE
    You are an Expert Instructional Designer and Assessment Specialist. Your goal is to generate a high-quality, rigorous quiz based on specific topics and a target experience level.

    ### GENERATION CONSTRAINTS
    1. **Accuracy**: Ensure all questions and answers are factually correct.
    2. **Relevance**: Questions must strictly adhere to the provided topics.
    3. **Experience Mapping**:
    - *Beginner*: Focus on definitions, basic concepts, and identification (Bloom's: Remember/Understand).
    - *Intermediate*: Focus on application, scenarios, and code snippet analysis (Bloom's: Apply/Analyze).
    - *Expert*: Focus on architectural decisions, edge cases, optimization, and debugging complex logic (Bloom's: Evaluate/Create).
    4. **Distractor Quality**: Wrong answers (distractors) must be plausible. Do not use "funny" or obviously wrong answers. Avoid "All of the above" or "None of the above" unless absolutely necessary.
    5. **Formatting**: The output must be valid JSON to ensure scalability and ease of parsing.

    ### OUTPUT FORMAT (JSON SCHEMA)

    {format_instructions}

    ### CONTENT GUIDELINES
    - If the topic is technical (programming), include code snippets in at least 30% of the questions.
    - Ensure the questions assess understanding, not just rote memorization.
    - The tone should be professional and academic.

    """

    user_template = """### QUIZ DETAILS
    - Target Audience Level: {experience_level}
    - Topic: {curriculum_title}
    - Sub-Topics: {topic_titles}
    - Number of Questions: {num_questions}

    ### INSTRUCTION
    Generate the quiz based on the System Role, Constraints, and Quiz details provided above. Output ONLY the raw JSON.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_template)
    ])

    prompt = prompt.partial(format_instructions=format_instructions)
    chain = prompt | llm | parser

    return chain


async def generate_quiz_response(
    curriculum_title: str,
    experience_level: str,
    topic_titles: list[str],
):
    if USE_MOCK_DATA:
        return load_mock_quiz()
    
    chain = create_generate_quiz_chain()
    try:
        result = await chain.ainvoke({
            "curriculum_title": curriculum_title,
            "experience_level": experience_level,
            "topic_titles": topic_titles,
            "num_questions": settings.QUIZ_NUM_QUESTIONS,
        })
        print(result)
        return result
    except Exception as e:
        print(f"Quiz error: {e}")
        return QuizBase(
            questions=[]
        )

def load_mock_quiz() -> QuizBase:
    """
    Helper function to load the local JSON file for testing.
    Uses pathlib to ensure it works across different operating systems.
    """
    try:
        # Construct path relative to where the app is running
        # Adjust 'tests' folder location if your structure differs
        base_dir = Path.cwd()
        file_path = base_dir / "tests" / "quiz.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Mock file not found at: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Validate that the JSON actually matches your Pydantic model
        # using .model_validate() (Pydantic v2) or .parse_obj() (Pydantic v1)
        return QuizBase.model_validate(data)
        
    except Exception as e:
        print(f"Mock Data Error: {e}")
        # Re-raise or handle gracefully depending on preference
        raise e