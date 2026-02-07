from __future__ import annotations
from typing import Optional


from pydantic import BaseModel


class PartyResponse(BaseModel):
    id: str
    name_ja: str
    name_short: str
    name_en: str
    color: str
    leader: str
    coalition_group: Optional[str]

    model_config = {"from_attributes": True}
