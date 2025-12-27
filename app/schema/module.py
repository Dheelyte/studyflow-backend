from pydantic import BaseModel, ConfigDict
from typing import Optional


class ModuleBase(BaseModel):
    title: str
    description: str
    order: int


class ModuleCreate(ModuleBase):
    playlist_id: int


class ModuleUpdate(ModuleBase):
    pass


class ModuleResponse(ModuleBase):
    id: int
    playlist_id: int
    
    model_config = ConfigDict(from_attributes=True)
