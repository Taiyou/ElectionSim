from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.prediction_pipeline import PredictionPipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def run_prediction_pipeline():
    logger.info("Scheduled prediction pipeline starting...")
    pipeline = PredictionPipeline()
    batch_id = await pipeline.run_full_prediction()
    logger.info("Scheduled prediction pipeline completed: %s", batch_id)


def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")

    hours = ",".join(str(h) for h in settings.schedule_hours_list)

    scheduler.add_job(
        run_prediction_pipeline,
        CronTrigger(hour=hours, minute=0, timezone="Asia/Tokyo"),
        id="prediction_pipeline",
        name="Election Prediction Pipeline",
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started, hours=%s JST", hours)
    return scheduler
