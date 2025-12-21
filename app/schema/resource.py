from pydantic import BaseModel, Field
from typing import List


class Resource(BaseModel):
    type: str = Field(..., description="Type of resource: Video, Article, etc.")
    label: str = Field(..., description="Display title for the resource")
    description: str
    resource_url: str = Field(..., description="An up-to-date and valid URL to one of the best live version of this resource, not a google search link. Make sure the URL doesn't lead to a resource that does not exist anymore")

class Lesson(BaseModel):
    lesson_title: str
    topics_covered: List[str]
    estimated_time: str
    resources: List[Resource]

class Module(BaseModel):
    module_id: int
    module_title: str
    lessons: List[Lesson]

class Curriculum(BaseModel):
    curriculum_title: str
    overview: str
    learning_objectives: List[str]
    modules: List[Module]

# Input model for the user request
class CurriculumRequest(BaseModel):
    topic: str
    experience_level: str = "Beginner"
    duration: str = "4 weeks"


# class ResourceCreate(ResourceBase):
#     module_id: int

# class ResourceUpdate(ResourceBase):
#     pass

# class ResourceResponse(ResourceBase):
#     id: int
#     module_id: int
    
#     class Config:
#         from_attributes = True
        