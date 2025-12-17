import uuid

from sqlalchemy import UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
