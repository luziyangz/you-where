import logging

from fastapi import APIRouter

from api.v2.rest_aliases import router as rest_aliases_router
from api.v2.core_reading import router as core_reading_router
from api.v2.store_reading import router as store_reading_router


router = APIRouter(tags=["v2"])
logger = logging.getLogger("youzainaye.v2")

router.include_router(store_reading_router)
router.include_router(core_reading_router)
router.include_router(rest_aliases_router)


@router.get("/_ping")
def ping_v2() -> dict:
    # v2 路由连通性探针，后续可删除。
    return {"ok": True, "version": "v2"}

