from __future__ import annotations
from typing import Optional


from pydantic import BaseModel


class CandidateResponse(BaseModel):
    id: int
    name: str
    name_kana: str
    party_id: str
    age: Optional[int]
    is_incumbent: bool
    previous_wins: int
    biography: Optional[str]
    dual_candidacy: bool

    model_config = {"from_attributes": True}
