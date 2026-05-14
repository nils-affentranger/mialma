from pydantic import BaseModel
from typing import List, Optional

class DomainBase(BaseModel):
    name: str
    description: Optional[str] = None
    state: str

class DomainCreate(DomainBase):
    pass

class Domain(DomainBase):
    class Config:
        from_attributes = True
