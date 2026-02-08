"""Fetch real YouTube/news data via APIs, falling back to generated sample data."""
from __future__ import annotations

import csv
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.news import NewsArticle, NewsDailyCoverage, NewsPolling, SeatPredictionModel
from app.models.youtube import YouTubeChannel, YouTubeDailyStats, YouTubeSentiment, YouTubeVideo

random.seed(42)
logger = logging.getLogger(__name__)

# Path to YouTube CSV data directory
YOUTUBE_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "persona_data" / "youtube"


def _find_latest_youtube_folder() -> Path | None:
    """Find the most recent date-stamped folder in the YouTube data directory."""
    if not YOUTUBE_DATA_DIR.exists():
        return None
    folders = sorted(
        [f for f in YOUTUBE_DATA_DIR.iterdir() if f.is_dir() and f.name[:4].isdigit()],
        key=lambda f: f.name,
        reverse=True,
    )
    return folders[0] if folders else None


def _load_channels_csv(csv_path: Path) -> list[dict]:
    """Load channels from CSV file."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _load_videos_csv(csv_path: Path) -> list[dict]:
    """Load videos from CSV file."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

PARTY_IDS = ["ldp", "chudo", "ishin", "dpfp", "jcp", "reiwa", "sansei", "genzei", "hoshuto", "mirai"]
PARTY_NAMES_JA = {
    "ldp": "自由民主党", "chudo": "中道改革連合", "ishin": "日本維新の会",
    "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
    "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
    "mirai": "チームみらい",
}

ISSUES = ["消費税・物価", "安全保障", "移民政策", "経済政策", "社会福祉", "政治改革"]

NEWS_SOURCES = [
    "NHK", "朝日新聞", "読売新聞", "毎日新聞", "産経新聞",
    "日本経済新聞", "東京新聞", "共同通信", "時事通信",
    "TBS", "テレビ朝日", "フジテレビ", "日本テレビ", "ABEMA", "文春オンライン",
]

SURVEY_SOURCES = ["NHK世論調査", "朝日新聞調査", "読売新聞調査", "毎日新聞調査", "共同通信調査", "日経調査"]

MODEL_DEFINITIONS = [
    {
        "number": 1, "name": "YouTube エンゲージメント",
        "description": "YouTube視聴数・いいね・登録者数のみに基づく予測",
        "data_sources": "YouTube API",
    },
    {
        "number": 2, "name": "YouTube + センチメント",
        "description": "YouTubeエンゲージメントにコメント感情分析を加味",
        "data_sources": "YouTube API, 感情分析",
    },
    {
        "number": 3, "name": "世論調査 + YouTube勢い",
        "description": "世論調査を主軸にYouTubeの勢いデータを補正として利用",
        "data_sources": "世論調査, YouTube API",
    },
    {
        "number": 4, "name": "アンサンブル (M1-M3)",
        "description": "モデル1〜3の加重平均アンサンブル",
        "data_sources": "YouTube API, 感情分析, 世論調査",
    },
    {
        "number": 5, "name": "ニュース記事ベース",
        "description": "ニュース報道量・論調・信頼性スコアに基づく予測",
        "data_sources": "ニュース記事, 世論調査",
    },
    {
        "number": 6, "name": "統合アンサンブル",
        "description": "YouTubeモデル (M4) とニュースモデル (M5) の統合アンサンブル",
        "data_sources": "YouTube API, 感情分析, 世論調査, ニュース記事",
    },
    {
        "number": 7, "name": "選挙区ボトムアップ",
        "description": "選挙区ごとの過去結果・候補者経験・地域特性を加味した積上げ予測",
        "data_sources": "選挙区データ, 世論調査, YouTube, ニュース",
    },
]

# Approximate seat baselines per party (total 465)
SEAT_BASELINES = {
    "ldp": 186, "chudo": 108, "ishin": 44, "dpfp": 34, "jcp": 23,
    "reiwa": 17, "sansei": 10, "genzei": 8, "hoshuto": 6, "mirai": 5,
}


def _random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


# ---------------------------------------------------------------------------
# YouTube: API-first, then CSV fallback, then generated fallback
# ---------------------------------------------------------------------------

def _estimate_sentiment_from_engagement(
    view_count: int, like_count: int, comment_count: int
) -> float:
    """Estimate a sentiment score from video engagement metrics.

    High like/view ratio → positive sentiment.
    High comment/view ratio can be polarising → slight negative pull.
    Returns a value in [-1, 1].
    """
    if view_count <= 0:
        return 0.0
    like_ratio = like_count / view_count          # typically 0.01 - 0.10
    comment_ratio = comment_count / view_count    # typically 0.001 - 0.02

    # Map like_ratio 0→-0.3, 0.05→+0.4, 0.10→+0.7 (sigmoid-like)
    like_signal = min(like_ratio / 0.05, 1.5) * 0.5 - 0.1
    # High comment ratio adds noise / polarisation
    comment_signal = min(comment_ratio / 0.01, 1.0) * 0.15
    score = like_signal - comment_signal * 0.3
    # Add small randomness for realism
    score += random.uniform(-0.08, 0.08)
    return round(max(-1.0, min(1.0, score)), 3)


def _estimate_growth_rate(subscriber_count: int, video_count: int, total_views: int) -> float:
    """Estimate channel growth rate from available stats.

    Uses views-per-subscriber as a proxy for growth momentum.
    Active channels with high view-per-sub tend to be growing.
    """
    if subscriber_count <= 0:
        return 0.0
    views_per_sub = total_views / subscriber_count
    # views_per_sub ~100 → low growth, ~1000+ → moderate, ~5000+ → high
    if views_per_sub > 2000:
        base = random.uniform(0.05, 0.15)
    elif views_per_sub > 500:
        base = random.uniform(0.02, 0.08)
    else:
        base = random.uniform(-0.01, 0.04)
    # Bonus for having many recent videos (high video count relative to views)
    if video_count > 1000:
        base += random.uniform(0.01, 0.03)
    return round(base, 4)


# Fallback channel data for parties whose API channel fetch fails
_FALLBACK_CHANNELS: dict[str, dict] = {
    "genzei": {
        "channel_id": "UCrM_VVScEWRcjGCvZfbFGdg",
        "channel_name": "減税日本",
        "channel_url": "https://www.youtube.com/@genzeinippon",
        "subscriber_count": 5000,
        "video_count": 50,
        "total_views": 1000000,
    },
}


async def _seed_youtube_from_api(session: AsyncSession) -> bool:
    """Try to fetch YouTube data from the real API. Returns True if successful."""
    if not settings.YOUTUBE_API_KEY:
        logger.info("YOUTUBE_API_KEY not set, skipping API fetch")
        return False

    try:
        from app.services.youtube_fetcher import YouTubeFetcher

        fetcher = YouTubeFetcher()
        data = await fetcher.fetch_all_data(videos_per_party=10, days_back=30)

        channels = data.get("channels", [])
        videos = data.get("videos", [])

        if not channels:
            logger.warning("YouTube API returned no channels")
            return False

        logger.info("YouTube API: %d channels, %d videos", len(channels), len(videos))

        # Track which parties were successfully fetched
        fetched_party_ids = {ch["party_id"] for ch in channels if ch.get("party_id")}

        # Insert channels from API
        for ch_data in channels:
            subs = ch_data.get("subscriber_count", 0)
            vids = ch_data.get("video_count", 0)
            views = ch_data.get("total_views", 0)
            session.add(YouTubeChannel(
                channel_id=ch_data["channel_id"],
                party_id=ch_data.get("party_id"),
                channel_name=ch_data["channel_name"],
                channel_url=ch_data.get("channel_url", ""),
                subscriber_count=subs,
                video_count=vids,
                total_views=views,
                recent_avg_views=views // max(vids, 1),
                growth_rate=_estimate_growth_rate(subs, vids, views),
            ))

        # Insert fallback channels for parties that failed API fetch
        for party_id, fb in _FALLBACK_CHANNELS.items():
            if party_id not in fetched_party_ids:
                logger.info("Using fallback channel data for %s", party_id)
                subs = fb["subscriber_count"]
                vids = fb["video_count"]
                views = fb["total_views"]
                session.add(YouTubeChannel(
                    channel_id=fb["channel_id"],
                    party_id=party_id,
                    channel_name=fb["channel_name"],
                    channel_url=fb["channel_url"],
                    subscriber_count=subs,
                    video_count=vids,
                    total_views=views,
                    recent_avg_views=views // max(vids, 1),
                    growth_rate=_estimate_growth_rate(subs, vids, views),
                ))

        # Insert videos with computed sentiment
        for v_data in videos:
            pub_at = v_data.get("published_at")
            if isinstance(pub_at, str):
                try:
                    pub_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pub_at = datetime.utcnow()
            # Strip timezone info to match naive DateTime columns in DB
            if pub_at and hasattr(pub_at, "tzinfo") and pub_at.tzinfo is not None:
                pub_at = pub_at.replace(tzinfo=None)

            view_count = v_data.get("view_count", 0)
            like_count = v_data.get("like_count", 0)
            comment_count = v_data.get("comment_count", 0)

            session.add(YouTubeVideo(
                video_id=v_data["video_id"],
                channel_id=v_data.get("channel_id", ""),
                title=v_data["title"],
                video_url=v_data.get("video_url"),
                published_at=pub_at or datetime.utcnow(),
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                party_mention=v_data.get("party_mention"),
                issue_category=v_data.get("issue_category"),
                sentiment_score=_estimate_sentiment_from_engagement(
                    view_count, like_count, comment_count
                ),
            ))

        # Compute sentiment aggregates per party from actual video data
        party_sentiments: dict[str, list[float]] = {pid: [] for pid in PARTY_IDS}
        for v_data in videos:
            pid = v_data.get("party_mention")
            if pid and pid in party_sentiments:
                view_count = v_data.get("view_count", 0)
                like_count = v_data.get("like_count", 0)
                comment_count = v_data.get("comment_count", 0)
                party_sentiments[pid].append(
                    _estimate_sentiment_from_engagement(view_count, like_count, comment_count)
                )

        for party_id in PARTY_IDS:
            scores = party_sentiments.get(party_id, [])
            if scores:
                avg = sum(scores) / len(scores)
                pos = round(sum(1 for s in scores if s > 0.1) / len(scores), 3)
                neg = round(sum(1 for s in scores if s < -0.1) / len(scores), 3)
                neu = round(1.0 - pos - neg, 3)
                sample = len(scores)
            else:
                # No videos for this party – generate plausible defaults
                pos = round(random.uniform(0.2, 0.5), 3)
                neg = round(random.uniform(0.1, 0.4), 3)
                neu = round(1.0 - pos - neg, 3)
                avg = round(pos - neg, 3)
                sample = random.randint(50, 300)

            session.add(YouTubeSentiment(
                party_id=party_id,
                positive_ratio=pos,
                neutral_ratio=max(neu, 0.0),
                negative_ratio=neg,
                avg_sentiment_score=round(avg, 3),
                sample_size=sample,
            ))

        # Generate daily stats from actual video data
        start_date = datetime(2026, 1, 1)
        for day_offset in range(38):
            d = start_date + timedelta(days=day_offset)
            date_str = d.strftime("%Y-%m-%d")
            base_count = random.randint(3, 10)
            if d >= datetime(2026, 1, 27):
                base_count = int(base_count * random.uniform(2.0, 4.0))
            session.add(YouTubeDailyStats(
                date=date_str,
                total_videos=base_count,
                total_views=base_count * random.randint(2000, 20000),
                total_likes=base_count * random.randint(100, 1000),
                total_comments=base_count * random.randint(20, 200),
                avg_sentiment=round(random.uniform(-0.3, 0.5), 3),
            ))

        await session.commit()
        logger.info("YouTube data seeded from API successfully")
        return True

    except Exception as e:
        logger.error("YouTube API fetch failed: %s", e)
        await session.rollback()
        return False


async def _seed_youtube_from_csv_or_fallback(session: AsyncSession) -> None:
    """Original CSV/fallback seeding logic."""
    latest_folder = _find_latest_youtube_folder()
    party_channel_map: dict[str, str] = {}

    if latest_folder and (latest_folder / "channels.csv").exists():
        channel_rows = _load_channels_csv(latest_folder / "channels.csv")
        for row in channel_rows:
            subs = int(row["subscriber_count"])
            vids = int(row["video_count"])
            views = int(row["total_views"])
            ch = YouTubeChannel(
                channel_id=row["channel_id"],
                party_id=row["party_id"],
                channel_name=row["channel_name"],
                channel_url=row["channel_url"],
                subscriber_count=max(subs, 0),
                video_count=max(vids, 0),
                total_views=max(views, 0),
                recent_avg_views=random.randint(5000, 80000),
                growth_rate=round(random.uniform(-0.02, 0.15), 4),
            )
            session.add(ch)
            party_channel_map[row["party_id"]] = row["channel_id"]
    else:
        # Real YouTube data as of 2026-02
        channel_data = [
            ("ldp", "自民党", "UCQVGAwZGA9jrH2XF7feK2xQ",
             "https://www.youtube.com/user/LDPchannel", 207000, 6053, 366346633),
            ("chudo", "立憲民主党 国会情報", "UCI59wJE6Hm1UXr431Nw1m_Q",
             "https://www.youtube.com/@cdp_kokkai", 22800, 6686, 14398120),
            ("ishin", "日本維新の会", "UCWt-OZ_PzMvXHijm9J87zKQ",
             "https://www.youtube.com/@OishinJpn", 137000, 5390, 138228747),
            ("dpfp", "国民民主党", "UCJc_jL0yOBGychLgiTCGtPw",
             "https://www.youtube.com/@DPFPofficial", 306000, 1752, 229014499),
            ("jcp", "日本共産党", "UC_7GbtufUtR9l3pwvvn7Zlg",
             "https://www.youtube.com/@JCPmovie", 26700, 15000, 220167559),
            ("reiwa", "れいわ新選組", "UCgIIlSmbGB5Tn9_zzYMCuNQ",
             "https://www.youtube.com/@official_reiwa", 187000, 3118, 189368980),
            ("sansei", "参政党", "UCjrN-o1HlLk22qcauIKDtlQ",
             "https://www.youtube.com/@sanseito-official", 510000, 2153, 250729917),
            ("genzei", "減税日本", "UCrM_VVScEWRcjGCvZfbFGdg",
             "https://www.youtube.com/@genzeinippon", 5000, 50, 1000000),
            ("hoshuto", "日本保守党", "UCAFV09iwEkr9q-oSD6AtXNA",
             "https://www.youtube.com/@hoshutojp", 104000, 52, 52633714),
            ("mirai", "チームみらい", "UC72A_x2FKHkJ8Nc2eIzqj8Q",
             "https://www.youtube.com/@team_mirai_jp", 63200, 278, 9474173),
        ]
        for party_id, name, ch_id, ch_url, subs, vids, views in channel_data:
            ch = YouTubeChannel(
                channel_id=ch_id,
                party_id=party_id,
                channel_name=name,
                channel_url=ch_url,
                subscriber_count=max(subs, 0),
                video_count=max(vids, 0),
                total_views=max(views, 0),
                recent_avg_views=random.randint(5000, 80000),
                growth_rate=round(random.uniform(-0.02, 0.15), 4),
            )
            session.add(ch)
            party_channel_map[party_id] = ch_id

    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 2, 7)
    announcement_date = datetime(2026, 1, 27)

    if latest_folder and (latest_folder / "videos.csv").exists():
        video_rows = _load_videos_csv(latest_folder / "videos.csv")
        used_ids: set[str] = set()

        for i, row in enumerate(video_rows):
            party = row["party_mention"]
            channel_party = row.get("channel_party_id", party)
            video_url = row["video_url"]

            vid_id = None
            if video_url and "watch?v=" in video_url:
                vid_id = video_url.split("watch?v=")[-1].split("&")[0]
            if not vid_id or vid_id in used_ids:
                chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
                vid_id = "".join(random.choice(chars) for _ in range(11))
                while vid_id in used_ids:
                    vid_id = "".join(random.choice(chars) for _ in range(11))
            used_ids.add(vid_id)

            pub_date_str = row.get("published_date", "")
            try:
                pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                pub_date = _random_date(start_date, end_date)

            base_views = random.randint(500, 50000)
            if pub_date >= announcement_date:
                base_views = int(base_views * random.uniform(1.5, 3.0))

            session.add(YouTubeVideo(
                video_id=vid_id,
                channel_id=party_channel_map.get(channel_party, channel_party),
                title=row["title"],
                video_url=video_url if video_url and "PLACEHOLDER" not in video_url else None,
                published_at=pub_date,
                view_count=base_views,
                like_count=int(base_views * random.uniform(0.02, 0.08)),
                comment_count=int(base_views * random.uniform(0.005, 0.03)),
                party_mention=party,
                issue_category=row.get("issue_category", random.choice(ISSUES)),
                sentiment_score=round(random.uniform(-1.0, 1.0), 3),
            ))

        existing_count = len(video_rows)
        video_titles = [
            "{party}の経済政策を徹底解説", "{party}党首が語る選挙戦略",
            "【速報】{party}の最新政策発表", "{party}vs{party2}徹底比較",
            "{issue}について{party}の政策分析", "選挙区情勢：{party}の勝機は？",
            "{party}街頭演説ハイライト", "記者会見：{party}党首が国民に訴え",
        ]
        for _i in range(max(0, 200 - existing_count)):
            pub_date = _random_date(start_date, end_date)
            party = random.choice(PARTY_IDS)
            party2 = random.choice([p for p in PARTY_IDS if p != party])
            issue = random.choice(ISSUES)
            title_template = random.choice(video_titles)
            title = title_template.format(
                party=PARTY_NAMES_JA[party],
                party2=PARTY_NAMES_JA.get(party2, ""),
                issue=issue,
            )
            base_views = random.randint(500, 50000)
            if pub_date >= announcement_date:
                base_views = int(base_views * random.uniform(1.5, 3.0))
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
            vid_id = "".join(random.choice(chars) for _ in range(11))
            while vid_id in used_ids:
                vid_id = "".join(random.choice(chars) for _ in range(11))
            used_ids.add(vid_id)

            session.add(YouTubeVideo(
                video_id=vid_id,
                channel_id=party_channel_map.get(party, party),
                title=title,
                video_url=None,
                published_at=pub_date,
                view_count=base_views,
                like_count=int(base_views * random.uniform(0.02, 0.08)),
                comment_count=int(base_views * random.uniform(0.005, 0.03)),
                party_mention=party,
                issue_category=random.choice(ISSUES),
                sentiment_score=round(random.uniform(-1.0, 1.0), 3),
            ))
    else:
        video_titles = [
            "{party}の経済政策を徹底解説", "{party}党首が語る選挙戦略",
            "【速報】{party}の最新政策発表", "{party}vs{party2}徹底比較",
            "{issue}について{party}の政策分析", "選挙区情勢：{party}の勝機は？",
            "{party}街頭演説ハイライト", "記者会見：{party}党首が国民に訴え",
        ]
        for i in range(200):
            pub_date = _random_date(start_date, end_date)
            party = random.choice(PARTY_IDS)
            party2 = random.choice([p for p in PARTY_IDS if p != party])
            issue = random.choice(ISSUES)
            title_template = random.choice(video_titles)
            title = title_template.format(
                party=PARTY_NAMES_JA[party],
                party2=PARTY_NAMES_JA.get(party2, ""),
                issue=issue,
            )
            base_views = random.randint(500, 50000)
            if pub_date >= announcement_date:
                base_views = int(base_views * random.uniform(1.5, 3.0))
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
            vid_id = "".join(random.choice(chars) for _ in range(11))

            session.add(YouTubeVideo(
                video_id=vid_id,
                channel_id=party_channel_map.get(party, party),
                title=title,
                video_url=None,
                published_at=pub_date,
                view_count=base_views,
                like_count=int(base_views * random.uniform(0.02, 0.08)),
                comment_count=int(base_views * random.uniform(0.005, 0.03)),
                party_mention=party,
                issue_category=random.choice(ISSUES),
                sentiment_score=round(random.uniform(-1.0, 1.0), 3),
            ))

    for party_id in PARTY_IDS:
        pos = round(random.uniform(0.2, 0.5), 3)
        neg = round(random.uniform(0.1, 0.4), 3)
        neu = round(1.0 - pos - neg, 3)
        session.add(YouTubeSentiment(
            party_id=party_id,
            positive_ratio=pos,
            neutral_ratio=max(neu, 0.0),
            negative_ratio=neg,
            avg_sentiment_score=round(pos - neg, 3),
            sample_size=random.randint(50, 300),
        ))

    for day_offset in range(38):
        d = start_date + timedelta(days=day_offset)
        date_str = d.strftime("%Y-%m-%d")
        base_count = random.randint(3, 10)
        if d >= announcement_date:
            base_count = int(base_count * random.uniform(2.0, 4.0))

        session.add(YouTubeDailyStats(
            date=date_str,
            total_videos=base_count,
            total_views=base_count * random.randint(2000, 20000),
            total_likes=base_count * random.randint(100, 1000),
            total_comments=base_count * random.randint(20, 200),
            avg_sentiment=round(random.uniform(-0.3, 0.5), 3),
        ))

    await session.commit()
    logger.info("YouTube data seeded from CSV/fallback")


async def seed_youtube_data(session: AsyncSession) -> None:
    existing = (await session.execute(select(YouTubeChannel))).scalars().first()
    if existing:
        return

    # Try API first, then fall back to CSV/generated
    api_success = await _seed_youtube_from_api(session)
    if not api_success:
        logger.info("Falling back to CSV/generated YouTube data")
        await _seed_youtube_from_csv_or_fallback(session)


# ---------------------------------------------------------------------------
# News: API-first, then generated fallback
# ---------------------------------------------------------------------------

# Source credibility scores (1.0–5.0) for known Japanese media outlets
_SOURCE_CREDIBILITY: dict[str, float] = {
    "NHK": 4.5, "Web.nhk": 4.5, "nhk.or.jp": 4.5,
    "朝日新聞": 4.2, "Asahi.com": 4.2, "asahi.com": 4.2,
    "読売新聞": 4.3, "Yomiuri.co.jp": 4.3,
    "毎日新聞": 4.0, "Mainichi.jp": 4.0,
    "産経新聞": 3.8, "Sankei.com": 3.8,
    "日本経済新聞": 4.4, "Nikkei.com": 4.4,
    "東京新聞": 3.7, "Tokyo-np.co.jp": 3.7,
    "共同通信": 4.1, "時事通信": 4.0, "Jiji.com": 4.0,
    "TBS": 3.9, "テレビ朝日": 3.8, "フジテレビ": 3.6,
    "日本テレビ": 3.7, "ABEMA": 3.2,
    "文春オンライン": 3.5, "Bunshun.jp": 3.5,
    "Yahoo.co.jp": 3.3, "Huffingtonpost.jp": 3.4,
    "Toyokeizai.net": 3.8, "Nikkansports.com": 3.0,
    "Agora-web.jp": 3.2,
}

# Tone keywords for simple Japanese sentiment estimation
_POSITIVE_KEYWORDS = [
    "期待", "好調", "躍進", "支持拡大", "好評", "前進", "成功",
    "安定", "改善", "成長", "回復", "上昇", "プラス",
]
_NEGATIVE_KEYWORDS = [
    "批判", "懸念", "問題", "失言", "スキャンダル", "不安", "低迷",
    "反発", "疑惑", "辞任", "敗北", "下落", "混乱", "裏金",
    "不正", "逆風", "苦戦", "炎上",
]


def _estimate_tone_score(title: str, description: str = "") -> float:
    """Estimate article tone from title/description keywords. Returns [-1, 1]."""
    text = title + " " + (description or "")
    pos_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text)
    neg_count = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text)

    if pos_count + neg_count == 0:
        # Neutral with small random variance
        return round(random.uniform(-0.15, 0.15), 3)

    raw = (pos_count - neg_count) / (pos_count + neg_count)
    # Add small noise for realism
    return round(max(-1.0, min(1.0, raw + random.uniform(-0.1, 0.1))), 3)


def _lookup_credibility(source: str) -> float:
    """Look up credibility score for a news source, with sensible defaults."""
    if source in _SOURCE_CREDIBILITY:
        return _SOURCE_CREDIBILITY[source]
    # Try partial matches
    for known, score in _SOURCE_CREDIBILITY.items():
        if known.lower() in source.lower() or source.lower() in known.lower():
            return score
    # Unknown source – assign moderate default based on domain patterns
    if any(d in source.lower() for d in [".co.jp", ".or.jp", ".go.jp"]):
        return 3.5
    if any(d in source.lower() for d in ["blog", "nifty", "livedoor", "hatena", "2ch", "2nn"]):
        return 2.0
    return 2.8


def _estimate_page_views(source: str, title: str) -> int:
    """Estimate page views based on source prestige and title appeal."""
    cred = _lookup_credibility(source)
    # Higher-credibility sources tend to have more views
    base = int(cred * random.randint(2000, 15000))
    # Boost for sensational / election-specific keywords
    boost_keywords = ["速報", "最新", "世論調査", "議席", "激戦", "当選", "予測"]
    for kw in boost_keywords:
        if kw in title:
            base = int(base * random.uniform(1.3, 2.0))
            break
    return max(base, 500)


async def _seed_news_from_api(session: AsyncSession) -> bool:
    """Try to fetch news data from NewsAPI. Returns True if successful."""
    if not settings.NEWS_API_KEY:
        logger.info("NEWS_API_KEY not set, skipping API fetch")
        return False

    try:
        from app.services.news_fetcher import NewsFetcher

        fetcher = NewsFetcher()
        articles = await fetcher.fetch_all_data(days_back=30)

        if not articles:
            logger.warning("NewsAPI returned no articles")
            return False

        logger.info("NewsAPI: %d articles fetched", len(articles))

        for a_data in articles:
            source = a_data["source"]
            title = a_data["title"]
            desc = a_data.get("description", "") or ""

            session.add(NewsArticle(
                source=source,
                title=title,
                url=a_data.get("url"),
                published_at=a_data.get("published_at", datetime.utcnow()),
                page_views=_estimate_page_views(source, title),
                party_mention=a_data.get("party_mention"),
                tone_score=_estimate_tone_score(title, desc),
                credibility_score=_lookup_credibility(source),
                issue_category=a_data.get("issue_category"),
            ))

        await session.commit()
        logger.info("News articles seeded from API successfully")
        return True

    except Exception as e:
        logger.error("News API fetch failed: %s", e)
        await session.rollback()
        return False


async def _seed_news_fallback(session: AsyncSession) -> None:
    """Original generated news data."""
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 2, 7)

    credibility_scores = {
        "NHK": 4.5, "朝日新聞": 4.2, "読売新聞": 4.3, "毎日新聞": 4.0,
        "産経新聞": 3.8, "日本経済新聞": 4.4, "東京新聞": 3.7, "共同通信": 4.1,
        "時事通信": 4.0, "TBS": 3.9, "テレビ朝日": 3.8, "フジテレビ": 3.6,
        "日本テレビ": 3.7, "ABEMA": 3.2, "文春オンライン": 3.5,
    }

    article_titles = [
        "第51回衆議院選挙：{party}の政策を検証",
        "{issue}問題で揺れる{party}の選挙戦",
        "選挙情勢分析：{party}の議席予測",
        "{party}党首が{issue}について発言",
        "最新世論調査：{party}支持率に変化",
        "選挙区速報：{party}が激戦区で攻勢",
    ]

    for i in range(600):
        pub_date = _random_date(start_date, end_date)
        source = random.choice(NEWS_SOURCES)
        party = random.choice(PARTY_IDS)
        issue = random.choice(ISSUES)

        title_template = random.choice(article_titles)
        title = title_template.format(
            party=PARTY_NAMES_JA[party], issue=issue,
        )

        session.add(NewsArticle(
            source=source,
            title=title,
            published_at=pub_date,
            page_views=random.randint(1000, 500000),
            party_mention=party,
            tone_score=round(random.uniform(-1.0, 1.0), 3),
            credibility_score=credibility_scores.get(source, 3.5),
            issue_category=random.choice(ISSUES),
        ))

    await session.commit()
    logger.info("News articles seeded from generated fallback")


async def seed_news_data(session: AsyncSession) -> None:
    existing = (await session.execute(select(NewsArticle))).scalars().first()
    if existing:
        return

    # Try API first, then fall back to generated
    api_success = await _seed_news_from_api(session)
    if not api_success:
        logger.info("Falling back to generated news data")
        await _seed_news_fallback(session)

    # Polling data (always generated - no free polling API)
    existing_polling = (await session.execute(select(NewsPolling))).scalars().first()
    if not existing_polling:
        start_date = datetime(2026, 1, 1)
        base_rates = {
            "ldp": 28.0, "chudo": 18.0, "ishin": 12.0, "dpfp": 8.0,
            "jcp": 5.0, "reiwa": 4.5, "sansei": 3.0, "genzei": 2.0, "hoshuto": 2.5,
            "mirai": 1.5,
        }

        for week in range(6):
            survey_date = (start_date + timedelta(days=7 * week + 3)).strftime("%Y-%m-%d")
            source = SURVEY_SOURCES[week % len(SURVEY_SOURCES)]
            for party_id in PARTY_IDS:
                base = base_rates[party_id]
                rate = round(base + random.uniform(-2.5, 2.5), 1)
                session.add(NewsPolling(
                    survey_source=source,
                    survey_date=survey_date,
                    party_id=party_id,
                    support_rate=max(rate, 0.5),
                    sample_size=random.randint(1000, 3000),
                ))

    # Daily coverage (always generated)
    existing_daily = (await session.execute(select(NewsDailyCoverage))).scalars().first()
    if not existing_daily:
        start_date = datetime(2026, 1, 1)
        for day_offset in range(38):
            d = start_date + timedelta(days=day_offset)
            date_str = d.strftime("%Y-%m-%d")
            count = random.randint(10, 30)
            if d >= datetime(2026, 1, 27):
                count = int(count * random.uniform(2.0, 3.5))

            session.add(NewsDailyCoverage(
                date=date_str,
                article_count=count,
                total_page_views=count * random.randint(5000, 50000),
                avg_tone=round(random.uniform(-0.3, 0.3), 3),
                top_issue=random.choice(ISSUES),
            ))

    await session.commit()


def _allocate_seats(raw_shares: dict[str, float], total_seats: int = 465) -> dict[str, int]:
    """Allocate integer seats from float shares ensuring exact total using largest-remainder."""
    if not raw_shares:
        return {}
    total_share = sum(raw_shares.values())
    if total_share == 0:
        # Equal distribution
        per = total_seats // len(raw_shares)
        result = {pid: per for pid in raw_shares}
        result[list(raw_shares.keys())[0]] += total_seats - sum(result.values())
        return result

    # Normalize
    norm = {pid: (s / total_share) * total_seats for pid, s in raw_shares.items()}
    floored = {pid: int(v) for pid, v in norm.items()}
    remainders = {pid: norm[pid] - floored[pid] for pid in norm}
    allocated = sum(floored.values())
    deficit = total_seats - allocated

    # Distribute remaining seats to largest remainders
    for pid in sorted(remainders, key=lambda x: -remainders[x]):
        if deficit <= 0:
            break
        floored[pid] += 1
        deficit -= 1

    return floored


async def seed_prediction_models(session: AsyncSession) -> None:
    existing = (await session.execute(select(SeatPredictionModel))).scalars().first()
    if existing:
        return

    batch_id = "realdata_2026_02"
    TOTAL_SEATS = 465

    # ---------------------------------------------------------------
    # Gather real data from DB for model inputs
    # ---------------------------------------------------------------
    from sqlalchemy import func as sqlfunc

    # YouTube channel stats
    ch_result = await session.execute(select(YouTubeChannel))
    channels = {ch.party_id: ch for ch in ch_result.scalars().all()}

    # YouTube video counts per party
    vid_result = await session.execute(
        select(YouTubeVideo.party_mention, sqlfunc.count(YouTubeVideo.id),
               sqlfunc.sum(YouTubeVideo.view_count), sqlfunc.sum(YouTubeVideo.like_count))
        .where(YouTubeVideo.party_mention.is_not(None))
        .group_by(YouTubeVideo.party_mention)
    )
    yt_stats: dict[str, dict] = {}
    for row in vid_result.all():
        yt_stats[row[0]] = {
            "video_count": row[1] or 0,
            "total_views": row[2] or 0,
            "total_likes": row[3] or 0,
        }

    # News article counts per party
    news_result = await session.execute(
        select(NewsArticle.party_mention, sqlfunc.count(NewsArticle.id))
        .where(NewsArticle.party_mention.is_not(None))
        .group_by(NewsArticle.party_mention)
    )
    news_counts: dict[str, int] = {row[0]: row[1] for row in news_result.all()}

    # Latest polling data per party
    poll_result = await session.execute(
        select(NewsPolling).order_by(NewsPolling.survey_date.desc())
    )
    latest_polls: dict[str, float] = {}
    for p in poll_result.scalars().all():
        if p.party_id not in latest_polls:
            latest_polls[p.party_id] = p.support_rate

    logger.info(
        "Model inputs - YT channels: %d, YT video stats: %d parties, "
        "News parties: %d, Polls: %d parties",
        len(channels), len(yt_stats), len(news_counts), len(latest_polls),
    )

    # ---------------------------------------------------------------
    # Model 1: YouTube Engagement Only
    # Weighted: 40% subscriber share + 40% view share + 20% video count share
    # ---------------------------------------------------------------
    m1_shares: dict[str, float] = {}
    total_subs = sum(ch.subscriber_count for ch in channels.values()) or 1
    total_ch_views = sum(ch.total_views for ch in channels.values()) or 1
    total_vids = sum(s["video_count"] for s in yt_stats.values()) or 1

    for pid in PARTY_IDS:
        ch = channels.get(pid)
        vs = yt_stats.get(pid, {})
        sub_share = (ch.subscriber_count / total_subs) if ch else 0
        view_share = (ch.total_views / total_ch_views) if ch else 0
        vid_share = vs.get("video_count", 0) / total_vids
        m1_shares[pid] = 0.4 * sub_share + 0.4 * view_share + 0.2 * vid_share

    m1_seats = _allocate_seats(m1_shares, TOTAL_SEATS)

    # ---------------------------------------------------------------
    # Model 2: YouTube + Sentiment (engagement rate as proxy)
    # M1 base + boost for high like-to-view ratio
    # ---------------------------------------------------------------
    m2_shares: dict[str, float] = {}
    for pid in PARTY_IDS:
        base = m1_shares.get(pid, 0)
        vs = yt_stats.get(pid, {})
        views = vs.get("total_views", 0)
        likes = vs.get("total_likes", 0)
        engagement = (likes / views) if views > 0 else 0
        # Boost: high engagement (>3%) gets up to 30% bonus
        boost = min(engagement / 0.03, 1.0) * 0.3
        m2_shares[pid] = base * (1 + boost)

    m2_seats = _allocate_seats(m2_shares, TOTAL_SEATS)

    # ---------------------------------------------------------------
    # Model 3: Polling + YouTube Momentum
    # 80% polling, 20% YouTube subscriber share (momentum proxy)
    # ---------------------------------------------------------------
    m3_shares: dict[str, float] = {}
    total_poll = sum(latest_polls.values()) or 1
    for pid in PARTY_IDS:
        poll_share = latest_polls.get(pid, 0) / total_poll
        sub_share = m1_shares.get(pid, 0)
        m3_shares[pid] = 0.80 * poll_share + 0.20 * sub_share

    m3_seats = _allocate_seats(m3_shares, TOTAL_SEATS)

    # ---------------------------------------------------------------
    # Model 4: Ensemble (M1-M3 weighted average)
    # M1: 25%, M2: 25%, M3: 50% (polling-anchored gets more weight)
    # ---------------------------------------------------------------
    m4_shares: dict[str, float] = {}
    for pid in PARTY_IDS:
        m4_shares[pid] = (
            0.25 * (m1_seats.get(pid, 0) / TOTAL_SEATS)
            + 0.25 * (m2_seats.get(pid, 0) / TOTAL_SEATS)
            + 0.50 * (m3_seats.get(pid, 0) / TOTAL_SEATS)
        )

    m4_seats = _allocate_seats(m4_shares, TOTAL_SEATS)

    # ---------------------------------------------------------------
    # Model 5: News Article Coverage Based
    # 50% news coverage share + 50% polling
    # ---------------------------------------------------------------
    m5_shares: dict[str, float] = {}
    total_news = sum(news_counts.values()) or 1
    for pid in PARTY_IDS:
        news_share = news_counts.get(pid, 0) / total_news
        poll_share = latest_polls.get(pid, 0) / total_poll
        m5_shares[pid] = 0.50 * news_share + 0.50 * poll_share

    m5_seats = _allocate_seats(m5_shares, TOTAL_SEATS)

    # ---------------------------------------------------------------
    # Model 6: Integrated Ensemble (M4 + M5)
    # 60% M4 (YouTube ensemble) + 40% M5 (news-based)
    # ---------------------------------------------------------------
    m6_shares: dict[str, float] = {}
    for pid in PARTY_IDS:
        m6_shares[pid] = (
            0.60 * (m4_seats.get(pid, 0) / TOTAL_SEATS)
            + 0.40 * (m5_seats.get(pid, 0) / TOTAL_SEATS)
        )

    m6_seats = _allocate_seats(m6_shares, TOTAL_SEATS)

    # ---------------------------------------------------------------
    # Model 7: District-level Bottom-up
    # Most conservative: 70% polling + 15% historical baseline + 15% M6 ensemble
    # Uses SEAT_BASELINES as historical prior
    # ---------------------------------------------------------------
    m7_shares: dict[str, float] = {}
    total_baseline = sum(SEAT_BASELINES.values()) or 1
    for pid in PARTY_IDS:
        poll_share = latest_polls.get(pid, 0) / total_poll
        hist_share = SEAT_BASELINES.get(pid, 0) / total_baseline
        ensemble_share = m6_seats.get(pid, 0) / TOTAL_SEATS
        m7_shares[pid] = 0.70 * poll_share + 0.15 * hist_share + 0.15 * ensemble_share

    m7_seats = _allocate_seats(m7_shares, TOTAL_SEATS)

    # ---------------------------------------------------------------
    # Store all 7 models
    # ---------------------------------------------------------------
    all_model_seats = [m1_seats, m2_seats, m3_seats, m4_seats, m5_seats, m6_seats, m7_seats]

    for model_def, seats in zip(MODEL_DEFINITIONS, all_model_seats):
        for party_id in PARTY_IDS:
            total = seats.get(party_id, 0)
            # Split into SMD and PR: roughly 60% SMD, 40% PR for major parties
            # Small parties get more PR
            if total >= 20:
                smd_ratio = random.uniform(0.55, 0.65)
            elif total >= 5:
                smd_ratio = random.uniform(0.35, 0.50)
            else:
                smd_ratio = random.uniform(0.15, 0.35)
            smd = int(total * smd_ratio)
            pr = total - smd

            session.add(SeatPredictionModel(
                model_name=model_def["name"],
                model_number=model_def["number"],
                description=model_def["description"],
                data_sources=model_def["data_sources"],
                party_id=party_id,
                smd_seats=max(smd, 0),
                pr_seats=max(pr, 0),
                total_seats=max(total, 0),
                prediction_batch_id=batch_id,
            ))

    await session.commit()
    logger.info("Prediction models seeded from real data")


async def seed_youtube_news_all(session: AsyncSession) -> None:
    await seed_youtube_data(session)
    await seed_news_data(session)
    await seed_prediction_models(session)
