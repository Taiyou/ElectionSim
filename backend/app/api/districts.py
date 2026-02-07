from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models import District
from app.schemas.district import DistrictDetailResponse, DistrictResponse

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("", response_model=list[DistrictResponse])
async def list_districts(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(District).order_by(District.prefecture_code, District.district_number)
    )
    return result.scalars().all()


@router.get("/{district_id}", response_model=DistrictDetailResponse)
async def get_district(
    district_id: str, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(District)
        .options(selectinload(District.candidates))
        .where(District.id == district_id)
    )
    district = result.scalars().first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    return district


@router.get("/prefecture/{prefecture_code}", response_model=list[DistrictResponse])
async def list_districts_by_prefecture(
    prefecture_code: int, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(District)
        .where(District.prefecture_code == prefecture_code)
        .order_by(District.district_number)
    )
    return result.scalars().all()
