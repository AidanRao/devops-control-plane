from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .api import routes as api_routes
from .ws import routes as ws_routes


app = FastAPI(title="DevOps Server")


@app.get("/health")
async def health() -> dict:
    """存活探针。"""

    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    """就绪探针"""

    return {"status": "ready"}


# REST API 前缀 /api
app.include_router(api_routes.router, prefix="/api")

# WebSocket 路由，直接挂在根路径下，路径为 /ws
app.include_router(ws_routes.router)

# 静态资源与管理 UI
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/ui", include_in_schema=False)
async def ui() -> FileResponse:
    """服务管理前端页面入口。"""

    return FileResponse("app/static/index.html", media_type="text/html")


def get_app() -> FastAPI:
    """uvicorn 可选的工厂方法。"""

    return app
