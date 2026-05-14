from typing import List, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

if TYPE_CHECKING:
    from .alias import Alias

class Domain(Base):
    __tablename__ = "domains"

    name: Mapped[str] = mapped_column(primary_key=True)
    description: Mapped[str | None]
    state: Mapped[str]
    
    aliases: Mapped[List["Alias"]] = relationship(back_populates="domain_rel", cascade="all, delete-orphan")
