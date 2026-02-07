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


# --- Map summary schemas ---

class PartyCount(BaseModel):
    party_id: str
    count: int


class CandidateBrief(BaseModel):
    name: str
    party_id: str
    is_incumbent: bool
    age: Optional[int] = None
    previous_wins: int = 0

    model_config = {"from_attributes": True}


class DistrictBrief(BaseModel):
    id: str
    name: str
    district_number: int
    candidate_count: int
    candidates: list[CandidateBrief] = []


class PrefectureMapSummary(BaseModel):
    prefecture_code: int
    prefecture_name: str
    total_districts: int
    total_candidates: int
    leading_party_id: str
    party_breakdown: list[PartyCount]
    districts: list[DistrictBrief]
