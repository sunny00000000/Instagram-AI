from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from cryptopulse.config import get_settings
from cryptopulse.db import ConversationRow
from cryptopulse.logging_config import configure_logging
from cryptopulse.runtime import Runtime, create_runtime
from cryptopulse.scheduler import create_scheduler
from cryptopulse.schemas import utc_now
from cryptopulse.schemas_messaging import InboundMessage

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
    version="0.2.0",
    description="Multi-agent crypto intelligence, publishing, inbox and partnership runtime",
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


@app.get("/webhooks/meta")
async def verify_meta_webhook(request: Request) -> Response:
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge", "")
    if mode == "subscribe" and token == settings.meta_webhook_verify_token:
        return Response(challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


async def _process_message(runtime: Runtime, message: InboundMessage) -> None:
    with runtime.database.session() as session:
        if session.query(ConversationRow).filter_by(message_id=message.message_id).first():
            return
    plan = await runtime.conversation_service.plan_reply(message)
    send_result = None
    if runtime.settings.auto_reply_enabled and plan.should_send:
        send_result = await runtime.messaging_client.send_text(message.sender_id, plan.reply_text)
    with runtime.database.session() as session:
        session.add(ConversationRow(
            platform=message.platform, sender_id=message.sender_id, message_id=message.message_id,
            inbound_text=message.text, category=plan.category.value, reply_text=plan.reply_text,
            requires_owner=plan.requires_owner,
            promotion_json=plan.promotion.model_dump(mode="json") if plan.promotion else {"send_result": send_result},
            created_at=utc_now(),
        ))
        session.commit()


@app.post("/webhooks/meta")
async def receive_meta_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    runtime: Runtime = request.app.state.runtime
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not runtime.messaging_client.verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    events = runtime.messaging_client.parse_events(payload)
    for event in events:
        background_tasks.add_task(_process_message, runtime, event)
    return JSONResponse({"accepted": True, "events": len(events)})
