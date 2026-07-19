from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

import uvicorn

from cryptopulse.config import Settings, get_settings
from cryptopulse.logging_config import configure_logging
from cryptopulse.runtime import create_runtime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cryptopulse")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser(
        "serve", help="Start API, scheduler, media server and health checks"
    )
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)

    subparsers.add_parser("run-once", help="Run one complete market-to-publish cycle")

    samples = subparsers.add_parser("generate-samples", help="Generate deterministic sample output")
    samples.add_argument("--output", default="sample_output")

    subparsers.add_parser("doctor", help="Validate configuration and local dependencies")
    return parser


async def run_once(settings: Settings) -> int:
    runtime = create_runtime(settings)
    try:
        summary = await runtime.orchestrator.run_once()
        print(json.dumps(summary.model_dump(mode="json"), indent=2, default=str))
        return 0 if summary.status == "completed" else 1
    finally:
        await runtime.close()


async def generate_samples(output: str) -> int:
    output_path = Path(output).resolve()
    if output_path.exists():
        shutil.rmtree(output_path)
    settings = Settings(
        app_env="test",
        dry_run=True,
        llm_provider="heuristic",
        media_root=output_path,
        database_url=f"sqlite:///{output_path / 'sample.db'}",
        retain_generated_media=True,
        brand_handle="@cryptopulse_sample",
        publish_reels=False,
    )
    runtime = create_runtime(settings, use_mock=True)
    try:
        summary = await runtime.orchestrator.run_once()
        (output_path / "run_summary.json").write_text(
            json.dumps(summary.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )
        return 0 if summary.status == "completed" else 1
    finally:
        await runtime.close()


def doctor(settings: Settings) -> int:
    checks = {
        "python": sys.version.split()[0],
        "ffmpeg": shutil.which("ffmpeg") or "missing (Reels will be skipped)",
        "media_root": str(settings.media_root),
        "database_url": settings.database_url,
        "dry_run": settings.dry_run,
        "llm_provider": settings.llm_provider,
        "gemini_key_present": bool(settings.gemini_api_key),
        "openai_key_present": bool(settings.openai_api_key),
        "live_publish_missing": settings.validate_live_publish_requirements(),
        "schedule_hours": settings.schedule_hour_list,
    }
    print(json.dumps(checks, indent=2))
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    if args.command == "serve":
        uvicorn.run("cryptopulse.api:app", host=args.host, port=args.port, proxy_headers=True)
        return
    if args.command == "run-once":
        raise SystemExit(asyncio.run(run_once(settings)))
    if args.command == "generate-samples":
        raise SystemExit(asyncio.run(generate_samples(args.output)))
    if args.command == "doctor":
        raise SystemExit(doctor(settings))


if __name__ == "__main__":
    main()
