from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class YouTubeChannelResponse(BaseModel):
    id: int
    channel_id: str
    party_id: Optional[str]
    channel_name: str
    channel_url: Optional[str]
    subscriber_count: int
    video_count: int
    total_views: int
    recent_avg_views: int
    growth_rate: float
    updated_at: datetime

    model_config = {"from_attributes": True}


class YouTubeVideoResponse(BaseModel):
    id: int
    video_id: str
    channel_id: str
    title: str
    video_url: Optional[str]
    published_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    party_mention: Optional[str]
    issue_category: Optional[str]
    sentiment_score: float
    collected_at: datetime

    model_config = {"from_attributes": True}


class YouTubeSentimentResponse(BaseModel):
    id: int
    party_id: str
    positive_ratio: float
    neutral_ratio: float
    negative_ratio: float
    avg_sentiment_score: float
    sample_size: int
    analysis_date: datetime

    model_config = {"from_attributes": True}


class YouTubeDailyStatsResponse(BaseModel):
    id: int
    date: str
    total_videos: int
    total_views: int
    total_likes: int
    total_comments: int
    avg_sentiment: float

    model_config = {"from_attributes": True}


class YouTubeSummaryResponse(BaseModel):
    total_videos: int
    total_views: int
    total_channels: int
    avg_sentiment: float
    channels: list[YouTubeChannelResponse]
    sentiments: list[YouTubeSentimentResponse]
    daily_stats: list[YouTubeDailyStatsResponse]
    recent_videos: list[YouTubeVideoResponse]
    issue_distribution: dict[str, int]
    party_video_counts: dict[str, int]
