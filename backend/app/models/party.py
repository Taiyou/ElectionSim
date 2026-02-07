from __future__ import annotations
from typing import Optional


from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name_ja: Mapped[str] = mapped_column(String(50))
    name_short: Mapped[str] = mapped_column(String(20))
    name_en: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(7))
    leader: Mapped[str] = mapped_column(String(50))
    coalition_group: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer)

    candidates = relationship("Candidate", back_populates="party")
