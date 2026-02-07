from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.news import (
    NewsArticle,
    NewsDailyCoverage,
    NewsPolling,
    SeatPredictionModel,
)
from app.schemas.news import (
    ModelComparisonEntry,
    ModelComparisonResponse,
    NewsArticleResponse,
    NewsDailyCoverageResponse,
    NewsPollingResponse,
    NewsSummaryResponse,
    SeatPredictionModelResponse,
)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/summary", response_model=NewsSummaryResponse)
async def get_news_summary(session: AsyncSession = Depends(get_session)):
    # Articles
    articles_result = await session.execute(
        select(NewsArticle).order_by(NewsArticle.page_views.desc()).limit(50)
    )
    articles = articles_result.scalars().all()

    # Daily coverage
    daily_result = await session.execute(
        select(NewsDailyCoverage).order_by(NewsDailyCoverage.date)
    )
    daily_coverage = daily_result.scalars().all()

    # Polling
    polling_result = await session.execute(
        select(NewsPolling).order_by(NewsPolling.survey_date)
    )
    polling = polling_result.scalars().all()

    # Aggregate stats
    total_result = await session.execute(
        select(
            func.count(NewsArticle.id),
            func.sum(NewsArticle.page_views),
        )
    )
    row = total_result.first()
    total_articles = row[0] or 0
    total_page_views = row[1] or 0

    # Unique sources
    source_result = await session.execute(
        select(NewsArticle.source, func.count(NewsArticle.id))
        .group_by(NewsArticle.source)
    )
    source_breakdown = {row[0]: row[1] for row in source_result.all()}

    # Average tone
    avg_tone_result = await session.execute(
        select(func.avg(NewsArticle.tone_score))
    )
    avg_tone = avg_tone_result.scalar() or 0.0

    # Party coverage counts
    party_result = await session.execute(
        select(NewsArticle.party_mention, func.count(NewsArticle.id))
        .where(NewsArticle.party_mention.is_not(None))
        .group_by(NewsArticle.party_mention)
    )
    party_coverage_counts = {row[0]: row[1] for row in party_result.all()}

    return NewsSummaryResponse(
        total_articles=total_articles,
        total_page_views=total_page_views,
        total_sources=len(source_breakdown),
        avg_tone=round(float(avg_tone), 3),
        articles=articles,
        daily_coverage=daily_coverage,
        polling=polling,
        source_breakdown=source_breakdown,
        party_coverage_counts=party_coverage_counts,
    )


@router.get("/articles", response_model=list[NewsArticleResponse])
async def get_articles(
    limit: int = 50,
    party: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(NewsArticle).order_by(NewsArticle.published_at.desc())
    if party:
        query = query.where(NewsArticle.party_mention == party)
    query = query.limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/polling", response_model=list[NewsPollingResponse])
async def get_polling(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(NewsPolling).order_by(NewsPolling.survey_date)
    )
    return result.scalars().all()


@router.get("/daily-coverage", response_model=list[NewsDailyCoverageResponse])
async def get_daily_coverage(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(NewsDailyCoverage).order_by(NewsDailyCoverage.date)
    )
    return result.scalars().all()


@router.get("/model-comparison", response_model=ModelComparisonResponse)
async def get_model_comparison(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SeatPredictionModel).order_by(
            SeatPredictionModel.model_number,
            SeatPredictionModel.party_id,
        )
    )
    models_data = result.scalars().all()

    # Group by model_number
    grouped: dict[int, list] = defaultdict(list)
    for m in models_data:
        grouped[m.model_number].append(m)

    party_ids_set: set[str] = set()
    entries = []
    for model_num in sorted(grouped.keys()):
        rows = grouped[model_num]
        predictions: dict[str, int] = {}
        for r in rows:
            predictions[r.party_id] = r.total_seats
            party_ids_set.add(r.party_id)
        entries.append(
            ModelComparisonEntry(
                model_number=model_num,
                model_name=rows[0].model_name,
                description=rows[0].description,
                data_sources=rows[0].data_sources,
                predictions=predictions,
            )
        )

    return ModelComparisonResponse(
        models=entries,
        party_ids=sorted(party_ids_set),
        majority_line=233,
    )


@router.get("/predictions", response_model=list[SeatPredictionModelResponse])
async def get_seat_predictions(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SeatPredictionModel).order_by(
            SeatPredictionModel.model_number,
            SeatPredictionModel.party_id,
        )
    )
    return result.scalars().all()
