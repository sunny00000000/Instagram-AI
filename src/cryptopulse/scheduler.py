from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cryptopulse.runtime import Runtime

logger = logging.getLogger(__name__)


def create_scheduler(runtime: Runtime) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=runtime.settings.timezone)
    hour_expression = ",".join(str(hour) for hour in runtime.settings.schedule_hour_list)
    scheduler.add_job(
        runtime.orchestrator.run_once,
        trigger=CronTrigger(hour=hour_expression, minute=0, timezone=runtime.settings.timezone),
        id="six-hour-market-cycle",
        name="CryptoPulse six-hour market cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
        replace_existing=True,
    )
    scheduler.add_job(
        runtime.orchestrator.learning_agent.evaluate_due_predictions,
        trigger=CronTrigger(minute=20, timezone=runtime.settings.timezone),
        id="prediction-evaluation",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        runtime.orchestrator.cleanup_agent.cleanup_expired_media,
        trigger=CronTrigger(minute=40, timezone=runtime.settings.timezone),
        id="media-cleanup",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler
