from uuid import uuid4

from fastapi import APIRouter, UploadFile

from app.core.errors import AppError
from app.models.schemas import AnalyzeAcceptedResponse

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/analyze", response_model=AnalyzeAcceptedResponse)
async def analyze_video(file: UploadFile) -> AnalyzeAcceptedResponse:
    if not file.filename:
        raise AppError(code="invalid_upload", message="filename is required")

    content_type = file.content_type or ""
    if not content_type.startswith("video/"):
        raise AppError(
            code="unsupported_media_type",
            message="uploaded file must be a video",
            status_code=415,
            details={"content_type": content_type},
        )

    return AnalyzeAcceptedResponse(
        task_id=str(uuid4()),
        status="accepted",
        message="analysis pipeline is not implemented in the initialization scaffold",
    )
