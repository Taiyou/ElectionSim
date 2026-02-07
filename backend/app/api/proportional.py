from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import ProportionalBlock
from app.models.prediction_history import ProportionalPrediction
from app.schemas.proportional import (
    BlockWithPredictions,
    ProportionalBlockResponse,
    ProportionalPredictionResponse,
)

router = APIRouter(prefix="/proportional", tags=["proportional"])


@router.get("/blocks", response_model=list[BlockWithPredictions])
async def list_blocks_with_predictions(
    session: AsyncSession = Depends(get_session),
):
    blocks_result = await session.execute(select(ProportionalBlock))
    blocks = blocks_result.scalars().all()

    result = []
    for block in blocks:
        preds_result = await session.execute(
            select(ProportionalPrediction)
            .where(ProportionalPrediction.block_id == block.id)
            .order_by(ProportionalPrediction.predicted_seats.desc())
        )
        preds = preds_result.scalars().all()

        result.append(
            BlockWithPredictions(
                block=ProportionalBlockResponse.model_validate(block),
                predictions=[
                    ProportionalPredictionResponse.model_validate(p) for p in preds
                ],
            )
        )
    return result


@router.get("/blocks/{block_id}", response_model=BlockWithPredictions)
async def get_block_detail(
    block_id: str, session: AsyncSession = Depends(get_session)
):
    block_result = await session.execute(
        select(ProportionalBlock).where(ProportionalBlock.id == block_id)
    )
    block = block_result.scalars().first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    preds_result = await session.execute(
        select(ProportionalPrediction)
        .where(ProportionalPrediction.block_id == block_id)
        .order_by(ProportionalPrediction.predicted_seats.desc())
    )
    preds = preds_result.scalars().all()

    return BlockWithPredictions(
        block=ProportionalBlockResponse.model_validate(block),
        predictions=[
            ProportionalPredictionResponse.model_validate(p) for p in preds
        ],
    )
