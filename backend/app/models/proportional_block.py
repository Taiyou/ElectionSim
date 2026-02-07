from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProportionalBlock(Base):
    __tablename__ = "proportional_blocks"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    total_seats: Mapped[int] = mapped_column(Integer)
    prefectures: Mapped[str] = mapped_column(Text)  # JSON array string
