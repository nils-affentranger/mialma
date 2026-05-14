from pydantic import BaseModel, EmailStr
from typing import List, Optional
from enum import Enum

class SyncActionKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class AliasBase(BaseModel):
    local_part: str
    is_internal: bool = False
    destinations: List[EmailStr]

class AliasCreate(AliasBase):
    pass

class AliasCreateRequest(BaseModel):
    is_internal: bool = False
    destinations: List[EmailStr]

class AliasUpdate(BaseModel):
    local_part: Optional[str] = None
    destinations: Optional[List[EmailStr]] = None
    is_internal: Optional[bool] = None

class Alias(AliasBase):
    address: str
    domain_name: str

    class Config:
        from_attributes = True
