from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.schemas.domain import Domain
from app.db.session import get_db
from app.models.domain import Domain as DomainModel

router = APIRouter()

@router.get("/", response_model=List[Domain])
async def list_domains(
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(DomainModel))
    domains = result.scalars().all()
    return domains
