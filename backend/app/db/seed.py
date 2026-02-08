from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Candidate, District, Party, ProportionalBlock

DATA_DIR = Path(__file__).parent.parent / "data"


async def seed_parties(session: AsyncSession) -> None:
    existing = (await session.execute(select(Party))).scalars().all()
    if existing:
        return

    with open(DATA_DIR / "parties.json", encoding="utf-8") as f:
        parties = json.load(f)

    for p in parties:
        session.add(Party(**p))
    await session.commit()


async def seed_proportional_blocks(session: AsyncSession) -> None:
    existing = (await session.execute(select(ProportionalBlock))).scalars().all()
    if existing:
        return

    with open(DATA_DIR / "proportional_blocks.json", encoding="utf-8") as f:
        blocks = json.load(f)

    for b in blocks:
        session.add(
            ProportionalBlock(
                id=b["id"],
                name=b["name"],
                total_seats=b["total_seats"],
                prefectures=json.dumps(b["prefectures"], ensure_ascii=False),
            )
        )
    await session.commit()


async def seed_districts_and_candidates(session: AsyncSession) -> None:
    existing = (await session.execute(select(District))).scalars().all()
    if existing:
        return

    with open(DATA_DIR / "districts_sample.json", encoding="utf-8") as f:
        districts = json.load(f)

    for d in districts:
        candidates_data = d.pop("candidates", [])
        session.add(District(**d))
        await session.flush()

        for c in candidates_data:
            session.add(Candidate(district_id=d["id"], **c))

    await session.commit()


async def seed_all(session: AsyncSession) -> None:
    await seed_parties(session)
    await seed_proportional_blocks(session)
    await seed_districts_and_candidates(session)

    from app.db.seed_predictions import seed_all_predictions
    await seed_all_predictions(session)

    from app.db.seed_youtube_news import seed_youtube_news_all
    await seed_youtube_news_all(session)
