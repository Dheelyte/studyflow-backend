from functools import lru_cache
import json
from pathlib import Path

from ..schema.resource import Curriculum


# Use lru_cache so the file is only read once and stored in memory
@lru_cache()
def get_prompt_template(file_name: str) -> str:
    prompt_path = Path(__file__).parent / "prompts" / file_name
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file {file_name} not found at {prompt_path}")
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def format_curriculum_prompt(topic: str, level: str, duration: str) -> str:
    # Load the base template
    template = get_prompt_template("curriculum_v1.txt")

    schema_string = json.dumps(Curriculum.model_json_schema(), indent=2)
    
    # Replace placeholders with actual user data
    return template.replace("{topic}", topic)\
                   .replace("{experience_level}", level)\
                   .replace("{duration}", duration)\
                   .replace("{json_schema}", schema_string)
