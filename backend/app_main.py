import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.v2.common import make_request_id
from api.v2.router import router as v2_router
from common.db import engine
from common.errors import ApiError
from common.models import Base


logger = logging.getLogger("youzainaye.v2")


def create_app() -> FastAPI:
    """创建主应用并挂载版本路由。"""
    Base.metadata.create_all(bind=engine)
    app = FastAPI(title="你在哪页 后端服务", version="2.0.0-skeleton")
    app.include_router(v2_router, prefix="/api/v2")

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": {},
                "request_id": make_request_id(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("未捕获异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": 50000,
                "message": "服务开小差了，请稍后再试",
                "data": {},
                "request_id": make_request_id(),
            },
        )

    @app.get("/health")
    def health() -> dict:
        # 保持健康检查接口稳定，便于联调与部署探活。
        return {"status": "ok"}

    return app


app = create_app()
