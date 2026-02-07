from pydantic import BaseModel


class ProportionalBlockResponse(BaseModel):
    id: str
    name: str
    total_seats: int
    prefectures: str  # JSON array string

    model_config = {"from_attributes": True}


class ProportionalPredictionResponse(BaseModel):
    block_id: str
    party_id: str
    predicted_seats: int
    vote_share_estimate: float
    analysis_summary: str
    prediction_batch_id: str

    model_config = {"from_attributes": True}


class BlockWithPredictions(BaseModel):
    block: ProportionalBlockResponse
    predictions: list[ProportionalPredictionResponse]
