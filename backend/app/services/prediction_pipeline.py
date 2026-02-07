from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import async_session
from app.models import (
    Candidate,
    District,
    Party,
    Prediction,
    PredictionHistory,
    ProportionalBlock,
)
from app.models.prediction_history import ProportionalPrediction
from app.services.claude_service import ClaudeService
from app.services.grok_service import GrokService
from app.services.perplexity_service import PerplexityService
from app.utils.logger import get_logger

logger = get_logger(__name__)
JST = ZoneInfo("Asia/Tokyo")

DATA_DIR = Path(__file__).parent.parent / "data"


class PredictionPipeline:
    """Orchestrates the full prediction pipeline.

    Uses separate DB sessions per operation to avoid SQLite concurrency issues.
    API calls (Perplexity + Grok) are still run in parallel per prefecture.
    """

    def __init__(self):
        self.perplexity = PerplexityService()
        self.grok = GrokService()
        self.claude = ClaudeService()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_prefectures(self) -> list[dict]:
        with open(DATA_DIR / "prefectures.json", encoding="utf-8") as f:
            return json.load(f)

    async def _load_districts_for_prefecture(self, prefecture_name: str) -> list[dict]:
        """Load districts with candidates using eager loading (avoids N+1)."""
        async with async_session() as session:
            result = await session.execute(
                select(District)
                .options(selectinload(District.candidates))
                .where(District.prefecture == prefecture_name)
            )
            districts = result.scalars().all()

            return [
                {
                    "id": d.id,
                    "name": d.name,
                    "area_description": d.area_description,
                    "candidates": [
                        {
                            "name": c.name,
                            "party_id": c.party_id,
                            "is_incumbent": c.is_incumbent,
                            "previous_wins": c.previous_wins,
                            "biography": c.biography,
                        }
                        for c in d.candidates
                    ],
                }
                for d in districts
            ]

    async def _load_parties(self) -> list[dict]:
        async with async_session() as session:
            result = await session.execute(select(Party).order_by(Party.sort_order))
            return [
                {
                    "id": p.id,
                    "name_ja": p.name_ja,
                    "name_short": p.name_short,
                    "coalition_group": p.coalition_group,
                }
                for p in result.scalars().all()
            ]

    # ------------------------------------------------------------------
    # Prefecture processing
    # ------------------------------------------------------------------

    async def _process_prefecture(self, prefecture: dict, batch_id: str) -> list[dict]:
        prefecture_name = prefecture["name"]
        districts = await self._load_districts_for_prefecture(prefecture_name)

        if not districts:
            logger.info("No districts found for %s, skipping", prefecture_name)
            return []

        logger.info("Processing %s (%d districts)", prefecture_name, len(districts))

        # Perplexity and Grok run in parallel (API calls, no DB)
        news_result, sns_result = await asyncio.gather(
            self.perplexity.analyze_prefecture(prefecture_name, districts),
            self.grok.analyze_prefecture(prefecture_name, districts),
        )

        logger.info("Perplexity + Grok done for %s, integrating with Claude...", prefecture_name)

        # Claude integration
        prediction = await self.claude.integrate_and_predict(
            prefecture_name, districts, news_result, sns_result
        )

        # Save to DB
        await self._save_district_predictions(prediction, batch_id)

        logger.info("Completed %s", prefecture_name)
        return prediction.get("districts", [])

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_district_predictions(self, prediction_data: dict, batch_id: str) -> None:
        async with async_session() as session:
            for dp in prediction_data.get("districts", []):
                district_id = dp.get("district_id", "")
                winner = dp.get("predicted_winner", {})
                winner_name = winner.get("name", "")
                winner_party = winner.get("party_id", "")

                # Find candidate ID
                candidate_result = await session.execute(
                    select(Candidate.id).where(
                        Candidate.district_id == district_id,
                        Candidate.name == winner_name,
                    )
                )
                candidate_id = candidate_result.scalar() or 0

                if candidate_id == 0:
                    logger.warning(
                        "Candidate '%s' not found in district %s", winner_name, district_id
                    )

                # Delete existing prediction for this district
                await session.execute(
                    delete(Prediction).where(Prediction.district_id == district_id)
                )

                session.add(Prediction(
                    district_id=district_id,
                    predicted_winner_candidate_id=candidate_id,
                    predicted_winner_party_id=winner_party,
                    confidence=dp.get("confidence", "low"),
                    confidence_score=dp.get("confidence_score", 0.5),
                    analysis_summary=dp.get("analysis", ""),
                    news_summary=dp.get("news_vs_sns_gap", ""),
                    sns_summary=dp.get("data_consistency", ""),
                    key_factors=json.dumps(dp.get("key_factors", []), ensure_ascii=False),
                    candidate_rankings=json.dumps(dp.get("candidate_ranking", []), ensure_ascii=False),
                    prediction_batch_id=batch_id,
                ))

                session.add(PredictionHistory(
                    district_id=district_id,
                    predicted_winner_party_id=winner_party,
                    confidence=dp.get("confidence", "low"),
                    confidence_score=dp.get("confidence_score", 0.5),
                    prediction_batch_id=batch_id,
                ))

            await session.commit()

    async def _save_proportional_predictions(
        self, block_id: str, result: dict, batch_id: str
    ) -> None:
        async with async_session() as session:
            await session.execute(
                delete(ProportionalPrediction).where(
                    ProportionalPrediction.block_id == block_id
                )
            )

            for pp in result.get("party_predictions", []):
                session.add(ProportionalPrediction(
                    block_id=block_id,
                    party_id=pp.get("party_id", ""),
                    predicted_seats=pp.get("predicted_seats", 0),
                    vote_share_estimate=pp.get("vote_share_estimate", 0.0),
                    analysis_summary=pp.get("reasoning", ""),
                    prediction_batch_id=batch_id,
                ))

            await session.commit()

    # ------------------------------------------------------------------
    # Proportional block processing
    # ------------------------------------------------------------------

    async def _process_proportional_blocks(self, batch_id: str) -> None:
        async with async_session() as session:
            result = await session.execute(select(ProportionalBlock))
            blocks_data = [
                {
                    "id": b.id,
                    "name": b.name,
                    "total_seats": b.total_seats,
                    "prefectures": b.prefectures,
                }
                for b in result.scalars().all()
            ]

        parties = await self._load_parties()

        for block_data in blocks_data:
            prefectures = json.loads(block_data["prefectures"])

            # Gather district predictions for this block
            async with async_session() as session:
                pred_result = await session.execute(
                    select(Prediction)
                    .join(District)
                    .where(
                        District.prefecture.in_(prefectures),
                        Prediction.prediction_batch_id == batch_id,
                    )
                )
                district_preds = [
                    {
                        "district_id": p.district_id,
                        "predicted_party": p.predicted_winner_party_id,
                        "confidence": p.confidence,
                    }
                    for p in pred_result.scalars().all()
                ]

            proportional_result = await self.claude.predict_proportional(
                block_id=block_data["id"],
                block_name=block_data["name"],
                total_seats=block_data["total_seats"],
                prefectures=prefectures,
                district_predictions=district_preds,
                parties_data=parties,
            )

            await self._save_proportional_predictions(
                block_data["id"], proportional_result, batch_id
            )
            logger.info("Proportional block %s completed", block_data["name"])

    # ------------------------------------------------------------------
    # Entrypoint
    # ------------------------------------------------------------------

    async def run_full_prediction(self) -> str:
        batch_id = datetime.now(JST).strftime("%Y-%m-%d_%H")
        logger.info("Starting prediction pipeline, batch_id=%s", batch_id)

        prefectures = await self._load_prefectures()

        # Process prefectures sequentially (SQLite doesn't support concurrent writes)
        for pref in prefectures:
            try:
                await self._process_prefecture(pref, batch_id)
            except Exception:
                logger.exception("Failed to process %s, continuing", pref["name"])

        # Proportional block predictions
        await self._process_proportional_blocks(batch_id)

        logger.info("Prediction pipeline completed, batch_id=%s", batch_id)
        return batch_id
