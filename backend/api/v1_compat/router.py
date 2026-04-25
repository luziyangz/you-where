from fastapi import APIRouter


router = APIRouter(tags=["v1-compat"])


@router.get("/_ping")
def ping_v1_compat() -> dict:
    # v1 兼容路由探针，便于迁移期快速验活。
    return {"ok": True, "compat": "v1"}

