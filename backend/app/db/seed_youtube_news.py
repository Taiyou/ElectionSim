"""Generate sample YouTube analytics, news articles, polling, and 7-model seat predictions."""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle, NewsDailyCoverage, NewsPolling, SeatPredictionModel
from app.models.youtube import YouTubeChannel, YouTubeDailyStats, YouTubeSentiment, YouTubeVideo

random.seed(42)

PARTY_IDS = ["ldp", "chudo", "ishin", "dpfp", "jcp", "reiwa", "sansei", "genzei", "hoshuto"]
PARTY_NAMES_JA = {
    "ldp": "自由民主党", "chudo": "中道改革連合", "ishin": "日本維新の会",
    "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
    "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
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
    "ldp": 190, "chudo": 110, "ishin": 45, "dpfp": 35, "jcp": 24,
    "reiwa": 18, "sansei": 10, "genzei": 8, "hoshuto": 6,
}


def _random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


async def seed_youtube_data(session: AsyncSession) -> None:
    existing = (await session.execute(select(YouTubeChannel))).scalars().first()
    if existing:
        return

    # Channels
    channel_data = [
        ("ldp", "自民党公式チャンネル", 350000, 4500, 200000000),
        ("chudo", "中道改革連合チャンネル", 180000, 2200, 80000000),
        ("ishin", "日本維新の会チャンネル", 220000, 3000, 120000000),
        ("dpfp", "国民民主党チャンネル", 150000, 1800, 60000000),
        ("jcp", "日本共産党チャンネル", 95000, 1500, 40000000),
        ("reiwa", "れいわ新選組チャンネル", 280000, 2800, 150000000),
        ("sansei", "参政党チャンネル", 120000, 1200, 35000000),
        ("genzei", "減税日本チャンネル", 85000, 800, 20000000),
        ("hoshuto", "日本保守党チャンネル", 160000, 1000, 45000000),
    ]

    channels = []
    for party_id, name, subs, vids, views in channel_data:
        ch = YouTubeChannel(
            channel_id=f"UC_{party_id}_sample",
            party_id=party_id,
            channel_name=name,
            subscriber_count=subs + random.randint(-10000, 10000),
            video_count=vids + random.randint(-100, 100),
            total_views=views + random.randint(-1000000, 1000000),
            recent_avg_views=random.randint(5000, 80000),
            growth_rate=round(random.uniform(-0.02, 0.15), 4),
        )
        channels.append(ch)
        session.add(ch)

    # Videos (200 sample)
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 2, 7)
    announcement_date = datetime(2026, 1, 27)

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

        # More views after announcement
        base_views = random.randint(500, 50000)
        if pub_date >= announcement_date:
            base_views = int(base_views * random.uniform(1.5, 3.0))

        session.add(YouTubeVideo(
            video_id=f"sample_vid_{i:04d}",
            channel_id=f"UC_{party}_sample",
            title=title,
            published_at=pub_date,
            view_count=base_views,
            like_count=int(base_views * random.uniform(0.02, 0.08)),
            comment_count=int(base_views * random.uniform(0.005, 0.03)),
            party_mention=party,
            issue_category=random.choice(ISSUES),
            sentiment_score=round(random.uniform(-1.0, 1.0), 3),
        ))

    # Sentiments per party
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

    # Daily stats (39 days: Jan 1 - Feb 7)
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


async def seed_news_data(session: AsyncSession) -> None:
    existing = (await session.execute(select(NewsArticle))).scalars().first()
    if existing:
        return

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

    # News articles (600)
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

    # Polling data (6 survey weeks)
    base_rates = {
        "ldp": 28.0, "chudo": 18.0, "ishin": 12.0, "dpfp": 8.0,
        "jcp": 5.0, "reiwa": 4.5, "sansei": 3.0, "genzei": 2.0, "hoshuto": 2.5,
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

    # Daily coverage (39 days)
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


async def seed_prediction_models(session: AsyncSession) -> None:
    existing = (await session.execute(select(SeatPredictionModel))).scalars().first()
    if existing:
        return

    batch_id = "models_sample_001"

    for model_def in MODEL_DEFINITIONS:
        # Generate per-party predictions with variation per model
        remaining = 465
        parties_left = list(PARTY_IDS)

        for idx, party_id in enumerate(PARTY_IDS):
            base = SEAT_BASELINES[party_id]

            # Each model has different variation characteristics
            model_num = model_def["number"]
            if model_num == 1:
                # YouTube only: more volatile, favors parties with YouTube presence
                variation = random.uniform(-15, 15)
                if party_id in ("reiwa", "hoshuto", "sansei"):
                    variation += random.uniform(3, 10)
            elif model_num == 2:
                variation = random.uniform(-12, 12)
            elif model_num == 3:
                # Polling-anchored: less volatile
                variation = random.uniform(-8, 8)
            elif model_num == 4:
                variation = random.uniform(-10, 10)
            elif model_num == 5:
                # News-based: slightly different bias
                variation = random.uniform(-10, 10)
                if party_id in ("ldp", "chudo"):
                    variation += random.uniform(-3, 5)
            elif model_num == 6:
                variation = random.uniform(-7, 7)
            else:
                # District-level: most stable
                variation = random.uniform(-5, 5)

            total = max(int(base + variation), 0)

            if idx == len(PARTY_IDS) - 1:
                # Last party gets remainder to ensure total=465
                total = max(remaining, 0)

            smd = int(total * random.uniform(0.5, 0.7))
            pr = total - smd

            remaining -= total

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


async def seed_youtube_news_all(session: AsyncSession) -> None:
    await seed_youtube_data(session)
    await seed_news_data(session)
    await seed_prediction_models(session)
