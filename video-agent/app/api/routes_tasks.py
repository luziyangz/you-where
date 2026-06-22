from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: str) -> dict[str, str]:
    return {"task_id": task_id, "status": "not_found"}
