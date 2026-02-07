from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NewsArticleResponse(BaseModel):
    id: int
    source: str
    title: str
    url: Optional[str]
    published_at: datetime
    page_views: int
    party_mention: Optional[str]
    tone_score: float
    credibility_score: float
    issue_category: Optional[str]
    collected_at: datetime

    model_config = {"from_attributes": True}


class NewsPollingResponse(BaseModel):
    id: int
    survey_source: str
    survey_date: str
    party_id: str
    support_rate: float
    sample_size: int

    model_config = {"from_attributes": True}


class NewsDailyCoverageResponse(BaseModel):
    id: int
    date: str
    article_count: int
    total_page_views: int
    avg_tone: float
    top_issue: Optional[str]

    model_config = {"from_attributes": True}


class SeatPredictionModelResponse(BaseModel):
    id: int
    model_name: str
    model_number: int
    description: str
    data_sources: str
    party_id: str
    smd_seats: int
    pr_seats: int
    total_seats: int
    prediction_batch_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class NewsSummaryResponse(BaseModel):
    total_articles: int
    total_page_views: int
    total_sources: int
    avg_tone: float
    articles: list[NewsArticleResponse]
    daily_coverage: list[NewsDailyCoverageResponse]
    polling: list[NewsPollingResponse]
    source_breakdown: dict[str, int]
    party_coverage_counts: dict[str, int]


class ModelComparisonEntry(BaseModel):
    model_number: int
    model_name: str
    description: str
    data_sources: str
    predictions: dict[str, int]  # party_id -> total_seats


class ModelComparisonResponse(BaseModel):
    models: list[ModelComparisonEntry]
    party_ids: list[str]
    majority_line: int
