from __future__ import annotations
from typing import Optional


from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"))
    name: Mapped[str] = mapped_column(String(50))
    name_kana: Mapped[str] = mapped_column(String(100))
    party_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_incumbent: Mapped[bool] = mapped_column(Boolean, default=False)
    previous_wins: Mapped[int] = mapped_column(Integer, default=0)
    biography: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proportional_block_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("proportional_blocks.id"), nullable=True
    )
    dual_candidacy: Mapped[bool] = mapped_column(Boolean, default=False)

    district = relationship("District", back_populates="candidates")
    party = relationship("Party", back_populates="candidates")
