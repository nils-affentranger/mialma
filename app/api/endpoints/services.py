from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.crud.sync import sync_migadu_data, get_alias_diff, push_alias_diff, stage_all_changes, discard_all_changes
from app.schemas.alias import Alias

router = APIRouter()

@router.post("/sync")
async def sync_migadu(db: AsyncSession = Depends(get_db)):
    try:
        await sync_migadu_data(db)
        return {"status": "success", "message": "Domains and aliases synced with Migadu"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diff")
async def diff_migadu(db: AsyncSession = Depends(get_db)):
    try:
        diff = await get_alias_diff(db)
        return {"status": "success", "diff": diff}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stage")
async def stage_all(db: AsyncSession = Depends(get_db)):
    try:
        await stage_all_changes(db)
        return {"status": "success", "message": "All pending changes staged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discard")
async def discard_all(db: AsyncSession = Depends(get_db)):
    try:
        await discard_all_changes(db)
        return {"status": "success", "message": "All pending changes discarded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/push")
async def push_migadu(db: AsyncSession = Depends(get_db)):
    try:
        diff = await push_alias_diff(db)
        return {"status": "success", "pushed": diff}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
