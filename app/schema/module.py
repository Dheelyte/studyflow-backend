from pydantic import BaseModel
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
    class Config:
        from_attributes = True