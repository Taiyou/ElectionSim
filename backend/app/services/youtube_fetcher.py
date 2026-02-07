"""Fetch real YouTube data using YouTube Data API v3."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Mapping of party_id to search keywords for finding relevant political videos
PARTY_SEARCH_KEYWORDS: dict[str, list[str]] = {
    "ldp": ["自民党", "自由民主党"],
    "chudo": ["立憲民主党", "中道改革"],
    "ishin": ["日本維新の会", "維新"],
    "dpfp": ["国民民主党"],
    "jcp": ["日本共産党", "共産党"],
    "reiwa": ["れいわ新選組", "れいわ"],
    "sansei": ["参政党"],
    "genzei": ["減税日本"],
    "hoshuto": ["日本保守党", "保守党"],
    "mirai": ["チームみらい"],
}

# Known YouTube channel IDs for Japanese political parties
PARTY_CHANNEL_IDS: dict[str, str] = {
    "ldp": "UCQVGAwZGA9jrH2XF7feK2xQ",
    "chudo": "UCI59wJE6Hm1UXr431Nw1m_Q",
    "ishin": "UCWt-OZ_PzMvXHijm9J87zKQ",
    "dpfp": "UCJc_jL0yOBGychLgiTCGtPw",
    "jcp": "UC_7GbtufUtR9l3pwvvn7Zlg",
    "reiwa": "UCgIIlSmbGB5Tn9_zzYMCuNQ",
    "sansei": "UCjrN-o1HlLk22qcauIKDtlQ",
    "genzei": "UCrM_VVScEWRcjGCvZfbFGdg",
    "hoshuto": "UCAFV09iwEkr9q-oSD6AtXNA",
    "mirai": "UC72A_x2FKHkJ8Nc2eIzqj8Q",
}

PARTY_NAMES_JA: dict[str, str] = {
    "ldp": "自由民主党",
    "chudo": "立憲民主党",
    "ishin": "日本維新の会",
    "dpfp": "国民民主党",
    "jcp": "日本共産党",
    "reiwa": "れいわ新選組",
    "sansei": "参政党",
    "genzei": "減税日本",
    "hoshuto": "日本保守党",
    "mirai": "チームみらい",
}


class YouTubeFetcher:
    """Fetches real data from YouTube Data API v3."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        if not self.api_key:
            raise ValueError(
                "YouTube API key not configured. Set YOUTUBE_API_KEY in .env"
            )

    async def _request(self, endpoint: str, params: dict[str, Any]) -> dict:
        """Make a request to YouTube Data API."""
        params["key"] = self.api_key
        url = f"{YOUTUBE_API_BASE}/{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.error(
                    "YouTube API %s returned %d: %s",
                    endpoint, resp.status_code, resp.text[:500],
                )
            resp.raise_for_status()
            return resp.json()

    async def fetch_channel_stats(self, channel_id: str) -> dict | None:
        """Fetch statistics for a single channel."""
        try:
            data = await self._request("channels", {
                "part": "snippet,statistics",
                "id": channel_id,
            })
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            return {
                "channel_id": channel_id,
                "channel_name": snippet.get("title", ""),
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "video_count": int(stats.get("videoCount", 0)),
                "total_views": int(stats.get("viewCount", 0)),
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
            }
        except Exception as e:
            logger.error("Failed to fetch channel %s: %s", channel_id, e)
            return None

    async def fetch_all_party_channels(self) -> list[dict]:
        """Fetch stats for all known party channels."""
        results = []
        for party_id, channel_id in PARTY_CHANNEL_IDS.items():
            data = await self.fetch_channel_stats(channel_id)
            if data:
                data["party_id"] = party_id
                results.append(data)
            else:
                logger.warning("No data for party %s channel %s", party_id, channel_id)
        return results

    async def search_party_videos(
        self,
        party_id: str,
        max_results: int = 10,
        published_after: datetime | None = None,
    ) -> list[dict]:
        """Search for recent videos related to a political party."""
        keywords = PARTY_SEARCH_KEYWORDS.get(party_id, [])
        if not keywords:
            return []

        query = " | ".join(keywords) + " 選挙"
        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "maxResults": max_results,
            "relevanceLanguage": "ja",
            "regionCode": "JP",
        }
        if published_after:
            params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            data = await self._request("search", params)
            items = data.get("items", [])

            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
            if not video_ids:
                return []

            # Fetch detailed stats for each video
            return await self.fetch_video_details(video_ids, party_id)
        except Exception as e:
            logger.error("Failed to search videos for %s: %s", party_id, e)
            return []

    async def fetch_video_details(self, video_ids: list[str], party_id: str = "") -> list[dict]:
        """Fetch detailed statistics for a list of video IDs."""
        if not video_ids:
            return []

        try:
            data = await self._request("videos", {
                "part": "snippet,statistics",
                "id": ",".join(video_ids),
            })
            results = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                video_id = item["id"]
                results.append({
                    "video_id": video_id,
                    "channel_id": snippet.get("channelId", ""),
                    "title": snippet.get("title", ""),
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "published_at": snippet.get("publishedAt", ""),
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "party_mention": party_id,
                })
            return results
        except Exception as e:
            logger.error("Failed to fetch video details: %s", e)
            return []

    async def fetch_channel_videos(
        self,
        channel_id: str,
        party_id: str,
        max_results: int = 10,
        published_after: datetime | None = None,
    ) -> list[dict]:
        """Fetch recent videos from a specific channel."""
        params: dict[str, Any] = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": max_results,
        }
        if published_after:
            params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            data = await self._request("search", params)
            items = data.get("items", [])
            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
            if not video_ids:
                return []
            return await self.fetch_video_details(video_ids, party_id)
        except Exception as e:
            logger.error("Failed to fetch channel videos for %s: %s", channel_id, e)
            return []

    async def fetch_all_data(
        self,
        videos_per_party: int = 10,
        days_back: int = 30,
    ) -> dict[str, Any]:
        """Fetch all YouTube data: channels + videos for all parties.

        Returns:
            dict with keys: "channels" (list[dict]), "videos" (list[dict])
        """
        published_after = datetime.utcnow() - timedelta(days=days_back)

        # Fetch channel stats
        channels = await self.fetch_all_party_channels()

        # Fetch videos per party (from both channel and search)
        all_videos: list[dict] = []
        seen_video_ids: set[str] = set()

        for party_id, channel_id in PARTY_CHANNEL_IDS.items():
            # Videos from the party's own channel
            ch_videos = await self.fetch_channel_videos(
                channel_id, party_id,
                max_results=videos_per_party // 2,
                published_after=published_after,
            )
            for v in ch_videos:
                if v["video_id"] not in seen_video_ids:
                    seen_video_ids.add(v["video_id"])
                    all_videos.append(v)

            # Search-based videos about the party
            search_videos = await self.search_party_videos(
                party_id,
                max_results=videos_per_party // 2,
                published_after=published_after,
            )
            for v in search_videos:
                if v["video_id"] not in seen_video_ids:
                    seen_video_ids.add(v["video_id"])
                    all_videos.append(v)

        logger.info(
            "Fetched %d channels and %d videos from YouTube API",
            len(channels), len(all_videos),
        )
        return {"channels": channels, "videos": all_videos}
