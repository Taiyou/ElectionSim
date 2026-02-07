from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    page_views: Mapped[int] = mapped_column(Integer, default=0)
    party_mention: Mapped[str] = mapped_column(String(30), nullable=True)
    tone_score: Mapped[float] = mapped_column(Float, default=0.0)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    issue_category: Mapped[str] = mapped_column(String(50), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NewsPolling(Base):
    __tablename__ = "news_polling"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_source: Mapped[str] = mapped_column(String(200))
    survey_date: Mapped[str] = mapped_column(String(10))
    party_id: Mapped[str] = mapped_column(String(30))
    support_rate: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)


class NewsDailyCoverage(Base):
    __tablename__ = "news_daily_coverage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10))
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    total_page_views: Mapped[int] = mapped_column(Integer, default=0)
    avg_tone: Mapped[float] = mapped_column(Float, default=0.0)
    top_issue: Mapped[str] = mapped_column(String(50), nullable=True)


class SeatPredictionModel(Base):
    __tablename__ = "seat_prediction_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100))
    model_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(500))
    data_sources: Mapped[str] = mapped_column(String(300))
    party_id: Mapped[str] = mapped_column(String(30))
    smd_seats: Mapped[int] = mapped_column(Integer, default=0)
    pr_seats: Mapped[int] = mapped_column(Integer, default=0)
    total_seats: Mapped[int] = mapped_column(Integer, default=0)
    prediction_batch_id: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
