from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from cryptopulse.config import get_settings
from cryptopulse.logging_config import configure_logging
from cryptopulse.runtime import Runtime, create_runtime
from cryptopulse.scheduler import create_scheduler

logger = logging.getLogger(__name__)
settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = create_runtime(settings)
    scheduler = create_scheduler(runtime)
    app.state.runtime = runtime
    app.state.scheduler = scheduler
    scheduler.start()
    if settings.run_on_startup:
        asyncio.create_task(runtime.orchestrator.run_once())
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await runtime.close()


app = FastAPI(
    title="CryptoPulse AI",
    version="0.1.0",
    description="Multi-agent crypto market intelligence and publishing runtime",
    lifespan=lifespan,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None,
)


@app.get("/health")
async def health(request: Request) -> dict:
    runtime: Runtime = request.app.state.runtime
    scheduler = request.app.state.scheduler
    return {
        "status": "ok",
        "environment": runtime.settings.app_env,
        "dry_run": runtime.settings.dry_run,
        "scheduler_running": scheduler.running,
        "schedule_hours_utc": runtime.settings.schedule_hour_list,
    }


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    runtime: Runtime = request.app.state.runtime
    missing = runtime.settings.validate_live_publish_requirements()
    status_code = 200 if not missing else 503
    return JSONResponse(
        {"ready": not missing, "missing_live_configuration": missing},
        status_code=status_code,
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/media/{relative_path:path}")
async def media(
    relative_path: str,
    request: Request,
    exp: int = Query(...),
    sig: str = Query(..., min_length=32),
) -> FileResponse:
    runtime: Runtime = request.app.state.runtime
    if not runtime.signer.verify(relative_path, exp, sig):
        raise HTTPException(status_code=403, detail="Invalid or expired media signature")
    root = runtime.settings.media_root.resolve()
    requested = (root / relative_path).resolve()
    if root not in requested.parents:
        raise HTTPException(status_code=403, detail="Invalid media path")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="Media not found")
    media_type = "video/mp4" if requested.suffix.lower() == ".mp4" else "image/png"
    return FileResponse(Path(requested), media_type=media_type)
