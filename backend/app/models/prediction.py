from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"))
    predicted_winner_candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    predicted_winner_party_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    confidence: Mapped[str] = mapped_column(String(10))  # high, medium, low
    confidence_score: Mapped[float] = mapped_column(Float)
    analysis_summary: Mapped[str] = mapped_column(Text)
    news_summary: Mapped[str] = mapped_column(Text)
    sns_summary: Mapped[str] = mapped_column(Text)
    key_factors: Mapped[str] = mapped_column(Text)  # JSON array
    candidate_rankings: Mapped[str] = mapped_column(Text)  # JSON
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    prediction_batch_id: Mapped[str] = mapped_column(String(30))

    district = relationship("District", back_populates="predictions")
    predicted_winner = relationship("Candidate", foreign_keys=[predicted_winner_candidate_id])
    predicted_party = relationship("Party", foreign_keys=[predicted_winner_party_id])
