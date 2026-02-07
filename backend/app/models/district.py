from __future__ import annotations
from typing import Optional


from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class District(Base):
    __tablename__ = "districts"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    prefecture: Mapped[str] = mapped_column(String(10))
    prefecture_code: Mapped[int] = mapped_column(Integer)
    district_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(50))
    area_description: Mapped[str] = mapped_column(Text)
    registered_voters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    candidates = relationship("Candidate", back_populates="district")
    predictions = relationship("Prediction", back_populates="district")
