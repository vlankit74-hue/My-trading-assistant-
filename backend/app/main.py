"""
Application entry point. Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import router as api_router
from app.api.websocket_routes import router as ws_router
from app.core.config import get_settings
from app.core.scheduler import start_background_jobs

logger = structlog.get_logger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.api_rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_app", config=settings.safe_dict())
    scheduler, streaming_tasks = start_background_jobs(settings)
    yield
    scheduler.shutdown(wait=False)
    for task in streaming_tasks:
        task.cancel()
    logger.info("app_shutdown_complete")


app = FastAPI(
    title="AI Trading Assistant — Gold & Bitcoin",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health_check(request: Request):
    return {"status": "ok", "env": settings.app_env}
