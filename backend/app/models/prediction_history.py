from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PredictionHistory(Base):
    __tablename__ = "prediction_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"))
    predicted_winner_party_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    confidence: Mapped[str] = mapped_column(String(10))
    confidence_score: Mapped[float] = mapped_column(Float)
    prediction_batch_id: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProportionalPrediction(Base):
    __tablename__ = "proportional_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_id: Mapped[str] = mapped_column(ForeignKey("proportional_blocks.id"))
    party_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    predicted_seats: Mapped[int] = mapped_column(Integer)
    vote_share_estimate: Mapped[float] = mapped_column(Float)
    analysis_summary: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    prediction_batch_id: Mapped[str] = mapped_column(String(30))
