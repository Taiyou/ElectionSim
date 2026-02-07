#!/usr/bin/env python3
"""手動で予測パイプラインを実行するスクリプト"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# backend ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db.seed import seed_all
from app.db.session import async_session, init_db
from app.services.prediction_pipeline import PredictionPipeline


async def main():
    print("Initializing database...")
    await init_db()

    async with async_session() as session:
        print("Seeding master data...")
        await seed_all(session)

    print("Starting prediction pipeline...")
    pipeline = PredictionPipeline()
    batch_id = await pipeline.run_full_prediction()
    print(f"Prediction pipeline completed. Batch ID: {batch_id}")


if __name__ == "__main__":
    asyncio.run(main())
