from __future__ import annotations
from typing import Optional


from datetime import datetime

from pydantic import BaseModel


class PredictionResponse(BaseModel):
    id: int
    district_id: str
    predicted_winner_party_id: str
    confidence: str
    confidence_score: float
    analysis_summary: str
    news_summary: str
    sns_summary: str
    key_factors: str  # JSON string
    candidate_rankings: str  # JSON string
    updated_at: datetime
    prediction_batch_id: str

    model_config = {"from_attributes": True}


class PredictionHistoryResponse(BaseModel):
    district_id: str
    predicted_winner_party_id: str
    confidence: str
    confidence_score: float
    prediction_batch_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PartySeatCount(BaseModel):
    party_id: str
    name_short: str
    color: str
    district_seats: int
    proportional_seats: int
    total_seats: int


class PartyCandidateCount(BaseModel):
    party_id: str
    name_short: str
    color: str
    count: int


class CandidateStats(BaseModel):
    total_candidates: int
    total_districts: int
    incumbent_count: int
    dual_candidacy_count: int
    party_breakdown: list[PartyCandidateCount]


class PredictionSummaryResponse(BaseModel):
    batch_id: str
    updated_at: Optional[datetime]
    total_seats: int = 465
    majority_line: int = 233
    party_seats: list[PartySeatCount]
    battleground_count: int
    confidence_distribution: dict[str, int]
    candidate_stats: Optional[CandidateStats] = None
