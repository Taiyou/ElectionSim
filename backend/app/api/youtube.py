from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.youtube import (
    YouTubeChannel,
    YouTubeDailyStats,
    YouTubeSentiment,
    YouTubeVideo,
)
from app.schemas.youtube import (
    YouTubeChannelResponse,
    YouTubeDailyStatsResponse,
    YouTubeSentimentResponse,
    YouTubeSummaryResponse,
    YouTubeVideoResponse,
)

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/summary", response_model=YouTubeSummaryResponse)
async def get_youtube_summary(session: AsyncSession = Depends(get_session)):
    # Channels
    channels_result = await session.execute(
        select(YouTubeChannel).order_by(YouTubeChannel.subscriber_count.desc())
    )
    channels = channels_result.scalars().all()

    # Sentiments
    sentiments_result = await session.execute(
        select(YouTubeSentiment).order_by(YouTubeSentiment.analysis_date.desc())
    )
    sentiments = sentiments_result.scalars().all()

    # Daily stats
    daily_result = await session.execute(
        select(YouTubeDailyStats).order_by(YouTubeDailyStats.date)
    )
    daily_stats = daily_result.scalars().all()

    # Recent videos
    videos_result = await session.execute(
        select(YouTubeVideo)
        .order_by(YouTubeVideo.view_count.desc())
        .limit(20)
    )
    recent_videos = videos_result.scalars().all()

    # Aggregate stats
    total_result = await session.execute(
        select(
            func.count(YouTubeVideo.id),
            func.sum(YouTubeVideo.view_count),
        )
    )
    row = total_result.first()
    total_videos = row[0] or 0
    total_views = row[1] or 0

    # Average sentiment
    avg_sent_result = await session.execute(
        select(func.avg(YouTubeVideo.sentiment_score))
    )
    avg_sentiment = avg_sent_result.scalar() or 0.0

    # Issue distribution
    issue_result = await session.execute(
        select(YouTubeVideo.issue_category, func.count(YouTubeVideo.id))
        .where(YouTubeVideo.issue_category.is_not(None))
        .group_by(YouTubeVideo.issue_category)
    )
    issue_distribution = {row[0]: row[1] for row in issue_result.all()}

    # Party video counts
    party_result = await session.execute(
        select(YouTubeVideo.party_mention, func.count(YouTubeVideo.id))
        .where(YouTubeVideo.party_mention.is_not(None))
        .group_by(YouTubeVideo.party_mention)
    )
    party_video_counts = {row[0]: row[1] for row in party_result.all()}

    return YouTubeSummaryResponse(
        total_videos=total_videos,
        total_views=total_views,
        total_channels=len(channels),
        avg_sentiment=round(float(avg_sentiment), 3),
        channels=channels,
        sentiments=sentiments,
        daily_stats=daily_stats,
        recent_videos=recent_videos,
        issue_distribution=issue_distribution,
        party_video_counts=party_video_counts,
    )


@router.get("/channels", response_model=list[YouTubeChannelResponse])
async def get_channels(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(YouTubeChannel).order_by(YouTubeChannel.subscriber_count.desc())
    )
    return result.scalars().all()


@router.get("/videos", response_model=list[YouTubeVideoResponse])
async def get_videos(
    limit: int = 50,
    party: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(YouTubeVideo).order_by(YouTubeVideo.view_count.desc())
    if party:
        query = query.where(YouTubeVideo.party_mention == party)
    query = query.limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/sentiments", response_model=list[YouTubeSentimentResponse])
async def get_sentiments(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(YouTubeSentiment).order_by(YouTubeSentiment.analysis_date.desc())
    )
    return result.scalars().all()


@router.get("/daily", response_model=list[YouTubeDailyStatsResponse])
async def get_daily_stats(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(YouTubeDailyStats).order_by(YouTubeDailyStats.date)
    )
    return result.scalars().all()
