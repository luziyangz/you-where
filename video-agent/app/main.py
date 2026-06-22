from fastapi import FastAPI

from app.api.routes_assets import router as assets_router
from app.api.routes_health import router as health_router
from app.api.routes_tasks import router as tasks_router
from app.api.routes_videos import router as videos_router
from app.core.config import settings
from app.core.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    register_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(videos_router, prefix="/api")
    app.include_router(tasks_router, prefix="/api")
    app.include_router(assets_router, prefix="/api")
    return app


app = create_app()
