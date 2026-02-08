"""API endpoints to trigger real data fetching from YouTube and News APIs."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.models.news import NewsArticle, NewsDailyCoverage
from app.models.youtube import YouTubeChannel, YouTubeDailyStats, YouTubeSentiment, YouTubeVideo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-fetch", tags=["data-fetch"])


class FetchResult(BaseModel):
    status: str
    youtube_channels: int = 0
    youtube_videos: int = 0
    news_articles: int = 0
    message: str = ""


@router.post("/youtube", response_model=FetchResult)
async def fetch_youtube_data(
    videos_per_party: int = 10,
    days_back: int = 30,
    session: AsyncSession = Depends(get_session),
):
    """Fetch real YouTube data and replace existing data in DB."""
    if not settings.YOUTUBE_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="YOUTUBE_API_KEY is not configured in .env",
        )

    from app.services.youtube_fetcher import YouTubeFetcher

    try:
        fetcher = YouTubeFetcher()
        data = await fetcher.fetch_all_data(
            videos_per_party=videos_per_party,
            days_back=days_back,
        )

        # Only clear old data if we have new data to replace it
        if not data["channels"] and not data["videos"]:
            raise HTTPException(
                status_code=502,
                detail="YouTube API returned no data (quota may be exceeded). Existing data preserved.",
            )

        # Clear old data
        await session.execute(delete(YouTubeVideo))
        await session.execute(delete(YouTubeSentiment))
        await session.execute(delete(YouTubeDailyStats))
        await session.execute(delete(YouTubeChannel))

        # Insert channels
        for ch_data in data["channels"]:
            session.add(YouTubeChannel(
                channel_id=ch_data["channel_id"],
                party_id=ch_data.get("party_id"),
                channel_name=ch_data["channel_name"],
                channel_url=ch_data.get("channel_url"),
                subscriber_count=ch_data.get("subscriber_count", 0),
                video_count=ch_data.get("video_count", 0),
                total_views=ch_data.get("total_views", 0),
                recent_avg_views=0,
                growth_rate=0.0,
            ))

        # Insert videos
        for v_data in data["videos"]:
            pub_at = v_data.get("published_at")
            if isinstance(pub_at, str):
                try:
                    pub_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pub_at = datetime.utcnow()
            # Strip timezone info to match naive DateTime columns in DB
            if pub_at and hasattr(pub_at, "tzinfo") and pub_at.tzinfo is not None:
                pub_at = pub_at.replace(tzinfo=None)

            session.add(YouTubeVideo(
                video_id=v_data["video_id"],
                channel_id=v_data.get("channel_id", ""),
                title=v_data["title"],
                video_url=v_data.get("video_url"),
                published_at=pub_at or datetime.utcnow(),
                view_count=v_data.get("view_count", 0),
                like_count=v_data.get("like_count", 0),
                comment_count=v_data.get("comment_count", 0),
                party_mention=v_data.get("party_mention"),
                issue_category=v_data.get("issue_category"),
                sentiment_score=0.0,
            ))

        await session.commit()

        return FetchResult(
            status="success",
            youtube_channels=len(data["channels"]),
            youtube_videos=len(data["videos"]),
            message="YouTube data fetched and stored successfully",
        )
    except Exception as e:
        logger.error("YouTube fetch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/news", response_model=FetchResult)
async def fetch_news_data(
    days_back: int = 30,
    session: AsyncSession = Depends(get_session),
):
    """Fetch real news data and replace existing articles in DB."""
    if not settings.NEWS_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="NEWS_API_KEY is not configured in .env",
        )

    from app.services.news_fetcher import NewsFetcher

    try:
        fetcher = NewsFetcher()
        articles = await fetcher.fetch_all_data(days_back=days_back)

        # Clear old articles (keep polling and models)
        await session.execute(delete(NewsArticle))
        await session.execute(delete(NewsDailyCoverage))

        # Insert articles
        for a_data in articles:
            session.add(NewsArticle(
                source=a_data["source"],
                title=a_data["title"],
                url=a_data.get("url"),
                published_at=a_data.get("published_at", datetime.utcnow()),
                page_views=0,  # NewsAPI doesn't provide page views
                party_mention=a_data.get("party_mention"),
                tone_score=0.0,  # Would need NLP analysis
                credibility_score=0.0,
                issue_category=a_data.get("issue_category"),
            ))

        await session.commit()

        return FetchResult(
            status="success",
            news_articles=len(articles),
            message="News data fetched and stored successfully",
        )
    except Exception as e:
        logger.error("News fetch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/all", response_model=FetchResult)
async def fetch_all_data(
    days_back: int = 30,
    session: AsyncSession = Depends(get_session),
):
    """Fetch both YouTube and news data."""
    yt_result = FetchResult(status="skipped")
    news_result = FetchResult(status="skipped")

    if settings.YOUTUBE_API_KEY:
        try:
            yt_result = await fetch_youtube_data(
                videos_per_party=10,
                days_back=days_back,
                session=session,
            )
        except HTTPException:
            yt_result = FetchResult(status="error", message="YouTube fetch failed")
    else:
        yt_result = FetchResult(status="skipped", message="YOUTUBE_API_KEY not set")

    if settings.NEWS_API_KEY:
        try:
            news_result = await fetch_news_data(
                days_back=days_back,
                session=session,
            )
        except HTTPException:
            news_result = FetchResult(status="error", message="News fetch failed")
    else:
        news_result = FetchResult(status="skipped", message="NEWS_API_KEY not set")

    return FetchResult(
        status="success",
        youtube_channels=yt_result.youtube_channels,
        youtube_videos=yt_result.youtube_videos,
        news_articles=news_result.news_articles,
        message=f"YouTube: {yt_result.message}; News: {news_result.message}",
    )


@router.get("/status")
async def get_fetch_status():
    """Check which API keys are configured."""
    return {
        "youtube_api_configured": bool(settings.YOUTUBE_API_KEY),
        "news_api_configured": bool(settings.NEWS_API_KEY),
        "youtube_api_key_prefix": settings.YOUTUBE_API_KEY[:8] + "..." if settings.YOUTUBE_API_KEY else None,
        "news_api_key_prefix": settings.NEWS_API_KEY[:8] + "..." if settings.NEWS_API_KEY else None,
    }
