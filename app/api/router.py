from fastapi import APIRouter
from app.api.endpoints import services, aliases, domains

api_router = APIRouter()
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(aliases.router, prefix="/aliases", tags=["aliases"])
api_router.include_router(domains.router, prefix="/domains", tags=["domains"])
