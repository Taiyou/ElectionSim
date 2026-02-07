"""Re-run predictions for prefectures that had JSON parse failures.

These are typically prefectures with many districts (10+) where
max_tokens was insufficient in the first run.
"""
from __future__ import annotations

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select, func

from app.db.session import async_session, init_db
from app.models import District, Prediction
from app.services.prediction_pipeline import PredictionPipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def find_failed_prefectures(batch_id: str) -> list[str]:
    """Find prefectures that have districts but no predictions."""
    async with async_session() as session:
        # Get all prefectures with districts
        result = await session.execute(
            select(District.prefecture, func.count(District.id))
            .group_by(District.prefecture)
        )
        all_prefectures = {row[0]: row[1] for row in result.all()}

        # Get prefectures with predictions
        result = await session.execute(
            select(District.prefecture, func.count(Prediction.id))
            .join(Prediction, Prediction.district_id == District.id)
            .where(Prediction.prediction_batch_id == batch_id)
            .group_by(District.prefecture)
        )
        predicted = {row[0]: row[1] for row in result.all()}

    failed = []
    for pref, district_count in all_prefectures.items():
        pred_count = predicted.get(pref, 0)
        if pred_count < district_count:
            failed.append(pref)
            logger.info(
                "%s: %d/%d districts predicted", pref, pred_count, district_count
            )

    return failed


async def retry_prefectures(batch_id: str, prefectures: list[str]) -> None:
    """Re-run pipeline for specific prefectures."""
    import json
    from pathlib import Path

    pipeline = PredictionPipeline()
    data_dir = Path(__file__).parent.parent / "backend" / "app" / "data"

    with open(data_dir / "prefectures.json", encoding="utf-8") as f:
        all_prefs = json.load(f)

    for pref_data in all_prefs:
        if pref_data["name"] in prefectures:
            logger.info("Retrying %s...", pref_data["name"])
            await pipeline._process_prefecture(pref_data, batch_id)


async def main():
    await init_db()

    # Find the latest batch_id
    async with async_session() as session:
        result = await session.execute(
            select(Prediction.prediction_batch_id)
            .order_by(Prediction.updated_at.desc())
            .limit(1)
        )
        row = result.scalar()
        if row:
            batch_id = row
        else:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            batch_id = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d_%H")

    logger.info("Using batch_id: %s", batch_id)

    failed = await find_failed_prefectures(batch_id)
    if not failed:
        logger.info("All prefectures have predictions!")
        return

    logger.info("Found %d prefectures to retry: %s", len(failed), ", ".join(failed))
    await retry_prefectures(batch_id, failed)
    logger.info("Retry complete!")


if __name__ == "__main__":
    asyncio.run(main())
