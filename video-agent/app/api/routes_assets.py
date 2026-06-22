from fastapi import APIRouter

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{asset_id}")
async def get_asset(asset_id: str) -> dict[str, str]:
    return {"asset_id": asset_id, "status": "not_found"}
