from __future__ import annotations
from typing import Optional


from pydantic import BaseModel

from app.schemas.candidate import CandidateResponse


class DistrictResponse(BaseModel):
    id: str
    prefecture: str
    prefecture_code: int
    district_number: int
    name: str
    area_description: str
    registered_voters: Optional[int]

    model_config = {"from_attributes": True}


class DistrictDetailResponse(DistrictResponse):
    candidates: list[CandidateResponse] = []
