from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, ForeignKey
from .base import Base


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"))
    order: Mapped[int] = mapped_column(Integer)
