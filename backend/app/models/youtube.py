from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class YouTubeChannel(Base):
    __tablename__ = "youtube_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(50), unique=True)
    party_id: Mapped[str] = mapped_column(String(30), nullable=True)
    channel_name: Mapped[str] = mapped_column(String(200))
    channel_url: Mapped[str] = mapped_column(String(500), nullable=True)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    recent_avg_views: Mapped[int] = mapped_column(Integer, default=0)
    growth_rate: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(50), unique=True)
    channel_id: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    video_url: Mapped[str] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    party_mention: Mapped[str] = mapped_column(String(30), nullable=True)
    issue_category: Mapped[str] = mapped_column(String(50), nullable=True)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class YouTubeSentiment(Base):
    __tablename__ = "youtube_sentiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    party_id: Mapped[str] = mapped_column(String(30))
    positive_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    neutral_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    negative_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    avg_sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    analysis_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class YouTubeDailyStats(Base):
    __tablename__ = "youtube_daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10))
    total_videos: Mapped[int] = mapped_column(Integer, default=0)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    total_likes: Mapped[int] = mapped_column(Integer, default=0)
    total_comments: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0.0)
