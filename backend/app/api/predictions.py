from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Candidate, District, Party, Prediction, PredictionHistory
from app.models.prediction_history import ProportionalPrediction
from app.schemas.prediction import (
    CandidateStats,
    PartyCandidateCount,
    PartySeatCount,
    PredictionHistoryResponse,
    PredictionResponse,
    PredictionSummaryResponse,
)

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/latest", response_model=list[PredictionResponse])
async def get_latest_predictions(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Prediction).order_by(Prediction.district_id)
    )
    return result.scalars().all()


@router.get("/summary", response_model=PredictionSummaryResponse)
async def get_prediction_summary(session: AsyncSession = Depends(get_session)):
    # Get latest batch id
    batch_result = await session.execute(
        select(Prediction.prediction_batch_id)
        .order_by(Prediction.updated_at.desc())
        .limit(1)
    )
    batch_row = batch_result.first()

    # Build candidate statistics regardless of whether predictions exist
    parties_result = await session.execute(
        select(Party).order_by(Party.sort_order)
    )
    parties = parties_result.scalars().all()

    total_candidates_result = await session.execute(
        select(func.count(Candidate.id))
    )
    total_candidates = total_candidates_result.scalar() or 0

    total_districts_result = await session.execute(
        select(func.count(District.id))
    )
    total_districts = total_districts_result.scalar() or 0

    incumbent_result = await session.execute(
        select(func.count(Candidate.id)).where(Candidate.is_incumbent.is_(True))
    )
    incumbent_count = incumbent_result.scalar() or 0

    dual_result = await session.execute(
        select(func.count(Candidate.id)).where(Candidate.dual_candidacy.is_(True))
    )
    dual_candidacy_count = dual_result.scalar() or 0

    party_candidate_result = await session.execute(
        select(Candidate.party_id, func.count(Candidate.id))
        .group_by(Candidate.party_id)
    )
    party_candidate_counts = {row[0]: row[1] for row in party_candidate_result.all()}

    party_candidate_list = []
    for party in parties:
        count = party_candidate_counts.get(party.id, 0)
        if count > 0:
            party_candidate_list.append(
                PartyCandidateCount(
                    party_id=party.id,
                    name_short=party.name_short,
                    color=party.color,
                    count=count,
                )
            )

    candidate_stats = CandidateStats(
        total_candidates=total_candidates,
        total_districts=total_districts,
        incumbent_count=incumbent_count,
        dual_candidacy_count=dual_candidacy_count,
        party_breakdown=party_candidate_list,
    )

    if not batch_row:
        return PredictionSummaryResponse(
            batch_id="none",
            updated_at=None,
            party_seats=[],
            battleground_count=0,
            confidence_distribution={"high": 0, "medium": 0, "low": 0},
            candidate_stats=candidate_stats,
        )

    batch_id = batch_row[0]

    # Get predictions for latest batch
    preds_result = await session.execute(
        select(Prediction).where(Prediction.prediction_batch_id == batch_id)
    )
    predictions = preds_result.scalars().all()

    # Count district seats by party
    district_seats: dict[str, int] = defaultdict(int)
    confidence_dist: dict[str, int] = defaultdict(int)
    latest_updated = None

    for p in predictions:
        district_seats[p.predicted_winner_party_id] += 1
        confidence_dist[p.confidence] += 1
        if latest_updated is None or p.updated_at > latest_updated:
            latest_updated = p.updated_at

    # Get proportional seats
    prop_result = await session.execute(
        select(
            ProportionalPrediction.party_id,
            func.sum(ProportionalPrediction.predicted_seats),
        )
        .where(ProportionalPrediction.prediction_batch_id == batch_id)
        .group_by(ProportionalPrediction.party_id)
    )
    proportional_seats: dict[str, int] = {}
    for row in prop_result:
        proportional_seats[row[0]] = int(row[1] or 0)

    party_seat_list = []
    for party in parties:
        d_seats = district_seats.get(party.id, 0)
        p_seats = proportional_seats.get(party.id, 0)
        if d_seats + p_seats > 0:
            party_seat_list.append(
                PartySeatCount(
                    party_id=party.id,
                    name_short=party.name_short,
                    color=party.color,
                    district_seats=d_seats,
                    proportional_seats=p_seats,
                    total_seats=d_seats + p_seats,
                )
            )

    battleground = confidence_dist.get("low", 0) + confidence_dist.get("medium", 0)

    return PredictionSummaryResponse(
        batch_id=batch_id,
        updated_at=latest_updated,
        party_seats=party_seat_list,
        battleground_count=battleground,
        confidence_distribution=dict(confidence_dist),
        candidate_stats=candidate_stats,
    )


@router.get("/district/{district_id}", response_model=PredictionResponse)
async def get_district_prediction(
    district_id: str, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Prediction).where(Prediction.district_id == district_id)
    )
    prediction = result.scalars().first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction


@router.get(
    "/district/{district_id}/history",
    response_model=list[PredictionHistoryResponse],
)
async def get_district_history(
    district_id: str, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(PredictionHistory)
        .where(PredictionHistory.district_id == district_id)
        .order_by(PredictionHistory.created_at)
    )
    return result.scalars().all()


@router.get("/battleground", response_model=list[PredictionResponse])
async def get_battleground(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Prediction)
        .where(Prediction.confidence.in_(["low", "medium"]))
        .order_by(Prediction.confidence_score)
    )
    return result.scalars().all()


@router.get("/prefecture/{prefecture_code}", response_model=list[PredictionResponse])
async def get_prefecture_predictions(
    prefecture_code: int, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Prediction)
        .join(District)
        .where(District.prefecture_code == prefecture_code)
        .order_by(District.district_number)
    )
    return result.scalars().all()
