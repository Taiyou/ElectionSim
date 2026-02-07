from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models import District
from app.schemas.district import (
    DistrictDetailResponse,
    DistrictResponse,
    PrefectureMapSummary,
)

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("", response_model=list[DistrictResponse])
async def list_districts(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(District).order_by(District.prefecture_code, District.district_number)
    )
    return result.scalars().all()


@router.get("/map-summary", response_model=list[PrefectureMapSummary])
async def map_summary(session: AsyncSession = Depends(get_session)):
    """Return candidate counts grouped by prefecture for map visualization."""
    result = await session.execute(
        select(District)
        .options(selectinload(District.candidates))
        .order_by(District.prefecture_code, District.district_number)
    )
    districts = result.scalars().all()

    # Group by prefecture
    pref_data: dict[int, dict] = {}
    for d in districts:
        code = d.prefecture_code
        if code not in pref_data:
            pref_data[code] = {
                "prefecture_code": code,
                "prefecture_name": d.prefecture,
                "districts": [],
                "party_counter": Counter(),
                "total_candidates": 0,
            }
        p = pref_data[code]
        cands = d.candidates or []
        p["districts"].append({
            "id": d.id,
            "name": d.name,
            "district_number": d.district_number,
            "candidate_count": len(cands),
            "candidates": [
                {
                    "name": c.name,
                    "party_id": c.party_id,
                    "is_incumbent": c.is_incumbent,
                    "age": c.age,
                    "previous_wins": c.previous_wins,
                }
                for c in cands
            ],
        })
        p["total_candidates"] += len(cands)
        for c in cands:
            p["party_counter"][c.party_id] += 1

    summaries = []
    for code in sorted(pref_data):
        p = pref_data[code]
        counter: Counter = p["party_counter"]
        leading = counter.most_common(1)[0][0] if counter else "independent"
        summaries.append(PrefectureMapSummary(
            prefecture_code=code,
            prefecture_name=p["prefecture_name"],
            total_districts=len(p["districts"]),
            total_candidates=p["total_candidates"],
            leading_party_id=leading,
            party_breakdown=[
                {"party_id": pid, "count": cnt}
                for pid, cnt in counter.most_common()
            ],
            districts=p["districts"],
        ))
    return summaries


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
