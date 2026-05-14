from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.schemas.alias import Alias, AliasUpdate, SyncActionKind, AliasCreateRequest
from app.db.session import get_db
from app.models.alias import Alias as AliasModel
from app.models.domain import Domain as DomainModel
from app.crud.sync import stage_alias_change, discard_alias_change

router = APIRouter()

async def validate_domain(domain: str, db: AsyncSession):
    result = await db.execute(select(DomainModel).where(DomainModel.name == domain))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Domain {domain} not found")

@router.post("/{domain}/{local_part}", response_model=Alias)
async def create_alias(
    domain: str,
    local_part: str,
    alias_in: AliasCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    await validate_domain(domain, db)
    address = f"{local_part}@{domain}"

    # Check if alias already exists
    result = await db.execute(select(AliasModel).where(AliasModel.address == address))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Alias already exists")

    try:
        # Save to local database
        db_alias = AliasModel(
            address=address,
            local_part=local_part,
            domain=domain,
            destinations=",".join(alias_in.destinations)
        )
        db.add(db_alias)
        await db.commit()
        await db.refresh(db_alias)

        return Alias(
            local_part=db_alias.local_part,
            destinations=db_alias.destinations.split(",") if db_alias.destinations else [],
            address=db_alias.address,
            domain_name=db_alias.domain
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{domain}", response_model=List[Alias])
async def list_aliases(
    domain: str,
    destination: str = None,
    db: AsyncSession = Depends(get_db)
):
    await validate_domain(domain, db)
    query = select(AliasModel).where(AliasModel.domain == domain)
    if destination:
        query = query.where(AliasModel.destinations.contains(destination))
        
    result = await db.execute(query)
    db_aliases = result.scalars().all()
    
    return [
        Alias(
            local_part=a.local_part,
            destinations=a.destinations.split(",") if a.destinations else [],
            address=a.address,
            domain_name=a.domain
        )
        for a in db_aliases
    ]

@router.get("/{domain}/{local_part}", response_model=Alias)
async def get_alias(
    domain: str,
    local_part: str,
    db: AsyncSession = Depends(get_db)
):
    await validate_domain(domain, db)
    address = f"{local_part}@{domain}"
    result = await db.execute(
        select(AliasModel).where(AliasModel.domain == domain, AliasModel.address == address)
    )
    db_alias = result.scalar_one_or_none()
    
    if not db_alias:
        raise HTTPException(status_code=404, detail="Alias not found")
        
    return Alias(
        local_part=db_alias.local_part,
        destinations=db_alias.destinations.split(",") if db_alias.destinations else [],
        address=db_alias.address,
        domain_name=db_alias.domain
    )

@router.patch("/{domain}/{local_part}", response_model=Alias)
async def update_alias(
    domain: str,
    local_part: str,
    alias_in: AliasUpdate,
    db: AsyncSession = Depends(get_db)
):
    await validate_domain(domain, db)
    address = f"{local_part}@{domain}"
    result = await db.execute(
        select(AliasModel).where(AliasModel.domain == domain, AliasModel.address == address)
    )
    db_alias = result.scalar_one_or_none()

    if not db_alias:
        raise HTTPException(status_code=404, detail="Alias not found")

    try:
        # Update local database
        if alias_in.local_part is not None:
            new_address = f"{alias_in.local_part}@{domain}"
            if new_address != db_alias.address:
                # Check if new address already exists
                check_result = await db.execute(select(AliasModel).where(AliasModel.address == new_address))
                if check_result.scalar_one_or_none():
                    raise HTTPException(status_code=400, detail="New alias address already exists")
                
                db_alias.address = new_address
                db_alias.local_part = alias_in.local_part

        if alias_in.destinations is not None:
            db_alias.destinations = ",".join(alias_in.destinations)

        await db.commit()
        await db.refresh(db_alias)

        return Alias(
            local_part=db_alias.local_part,
            destinations=db_alias.destinations.split(",") if db_alias.destinations else [],
            address=db_alias.address,
            domain_name=db_alias.domain
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{domain}/{local_part}", status_code=204)
async def delete_alias(
    domain: str,
    local_part: str,
    db: AsyncSession = Depends(get_db)
):
    await validate_domain(domain, db)
    address = f"{local_part}@{domain}"
    result = await db.execute(
        select(AliasModel).where(AliasModel.domain == domain, AliasModel.address == address)
    )
    db_alias = result.scalar_one_or_none()

    if not db_alias:
        raise HTTPException(status_code=404, detail="Alias not found")

    try:
        # Stage deletion instead of immediate delete
        await stage_alias_change(db, domain, local_part, SyncActionKind.DELETE)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stage/{domain}/{local_part}")
async def stage_alias(
    domain: str,
    local_part: str,
    action: SyncActionKind,
    db: AsyncSession = Depends(get_db)
):
    await validate_domain(domain, db)
    try:
        await stage_alias_change(db, domain, local_part, action)
        return {"status": "success", "message": f"Change for {local_part}@{domain} staged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discard/{domain}/{local_part}")
async def discard_alias(
    domain: str,
    local_part: str,
    action: SyncActionKind,
    db: AsyncSession = Depends(get_db)
):
    await validate_domain(domain, db)
    try:
        await discard_alias_change(db, domain, local_part, action)
        return {"status": "success", "message": f"Change for {local_part}@{domain} discarded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
