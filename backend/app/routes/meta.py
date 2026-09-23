from fastapi import APIRouter

from app.schemas.meta import ProvidersOut

router = APIRouter(tags=["meta"])


@router.get("/api/meta/providers", operation_id="get_providers", response_model=ProvidersOut)
async def get_providers() -> ProvidersOut:
    raise NotImplementedError
