import enum
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

if TYPE_CHECKING:
    from .domain import Domain

class SyncActionKind(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class Alias(Base):
    __tablename__ = "aliases"

    address: Mapped[str] = mapped_column(primary_key=True)
    local_part: Mapped[str]
    domain: Mapped[str] = mapped_column(ForeignKey("domains.name"))
    is_internal: Mapped[bool] = mapped_column(default=False)
    destinations: Mapped[str]  # Stored as CSV string

    domain_rel: Mapped["Domain"] = relationship(back_populates="aliases")


class StagedChange(Base):
    __tablename__ = "staged_changes"

    address: Mapped[str] = mapped_column(primary_key=True)
    action: Mapped[SyncActionKind] = mapped_column(Enum(SyncActionKind))
