"""Fetch real news data using NewsAPI.org."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2"

# Search keywords for election-related news (Japanese)
ELECTION_KEYWORDS = [
    "衆議院選挙",
    "衆院選",
    "日本 選挙",
    "日本 政治",
]

# Party-specific search keywords
PARTY_KEYWORDS: dict[str, list[str]] = {
    "ldp": ["自民党", "自由民主党"],
    "chudo": ["立憲民主党"],
    "ishin": ["維新の会", "維新"],
    "dpfp": ["国民民主党"],
    "jcp": ["共産党"],
    "reiwa": ["れいわ新選組", "れいわ"],
    "sansei": ["参政党"],
    "genzei": ["減税日本"],
    "hoshuto": ["日本保守党"],
    "mirai": ["チームみらい"],
}

# Hiragana and Katakana regex - these are unique to Japanese
# (CJK kanji alone could be Chinese, so we require kana)
_HIRAGANA_PATTERN = re.compile(r"[\u3040-\u309F]")
_KATAKANA_PATTERN = re.compile(r"[\u30A0-\u30FF]")


def _is_japanese_text(text: str) -> bool:
    """Check if text contains Japanese-specific characters (hiragana or katakana).

    Chinese text uses only CJK characters without kana,
    so checking for hiragana/katakana effectively filters out Chinese articles.
    """
    return bool(_HIRAGANA_PATTERN.search(text) or _KATAKANA_PATTERN.search(text))


def _detect_party_mention(title: str, description: str = "") -> str | None:
    """Detect which party is mentioned in an article title/description."""
    text = title + " " + (description or "")
    for party_id, keywords in PARTY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return party_id
    return None


def _detect_issue_category(title: str, description: str = "") -> str | None:
    """Detect the issue category from article text."""
    text = title + " " + (description or "")
    issue_keywords = {
        "消費税・物価": ["消費税", "物価", "インフレ", "値上げ", "増税"],
        "安全保障": ["安全保障", "防衛", "軍事", "自衛隊", "安保"],
        "移民政策": ["移民", "外国人", "入管", "技能実習"],
        "経済政策": ["経済", "景気", "賃金", "GDP", "金融", "株"],
        "社会福祉": ["社会福祉", "年金", "医療", "介護", "子育て", "少子化"],
        "政治改革": ["政治改革", "選挙制度", "裏金", "政治資金", "透明性"],
    }
    for category, keywords in issue_keywords.items():
        for kw in keywords:
            if kw in text:
                return category
    return None


class NewsFetcher:
    """Fetches real news articles from NewsAPI.org."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.NEWS_API_KEY
        if not self.api_key:
            raise ValueError(
                "News API key not configured. Set NEWS_API_KEY in .env"
            )

    async def _request(self, endpoint: str, params: dict[str, Any]) -> dict:
        """Make a request to NewsAPI."""
        params["apiKey"] = self.api_key
        url = f"{NEWSAPI_BASE}/{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.error(
                    "NewsAPI %s returned %d: %s",
                    endpoint, resp.status_code, resp.text[:500],
                )
            resp.raise_for_status()
            return resp.json()

    async def fetch_election_news(
        self,
        query: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page_size: int = 100,
        page: int = 1,
        sort_by: str = "publishedAt",
    ) -> list[dict]:
        """Fetch election-related news articles.

        Note: NewsAPI free plan may not support language=ja properly,
        so we search with Japanese keywords without the language filter
        and post-filter for Japanese content.
        """
        if not query:
            query = " OR ".join(ELECTION_KEYWORDS)

        params: dict[str, Any] = {
            "q": query,
            "pageSize": min(page_size, 100),
            "page": page,
            "sortBy": sort_by,
        }
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")

        try:
            data = await self._request("everything", params)
            articles = data.get("articles", [])
            total_results = data.get("totalResults", 0)
            logger.info(
                "NewsAPI returned %d articles (total: %d) for query: %s",
                len(articles), total_results, query,
            )
            return self._normalize_articles(articles)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 426:
                logger.warning(
                    "NewsAPI free plan limitation: cannot search older than 1 month. "
                    "Trying with recent dates."
                )
                params["from"] = (datetime.utcnow() - timedelta(days=29)).strftime("%Y-%m-%d")
                params.pop("to", None)
                try:
                    data = await self._request("everything", params)
                    return self._normalize_articles(data.get("articles", []))
                except Exception as retry_err:
                    logger.error("NewsAPI retry failed: %s", retry_err)
                    return []
            logger.error("NewsAPI HTTP error: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to fetch news: %s", e)
            return []

    async def fetch_party_news(
        self,
        party_id: str,
        days_back: int = 30,
        max_articles: int = 20,
    ) -> list[dict]:
        """Fetch news articles specifically about a political party."""
        keywords = PARTY_KEYWORDS.get(party_id, [])
        if not keywords:
            return []

        party_query = " OR ".join(f'"{kw}"' for kw in keywords)
        query = f"({party_query}) AND (選挙 OR 政治 OR 政策)"

        from_date = datetime.utcnow() - timedelta(days=days_back)
        articles = await self.fetch_election_news(
            query=query,
            from_date=from_date,
            page_size=max_articles,
        )
        for article in articles:
            if not article.get("party_mention"):
                article["party_mention"] = party_id
        return articles

    async def fetch_top_headlines(self, page_size: int = 20) -> list[dict]:
        """Fetch top headlines from Japan related to politics."""
        try:
            data = await self._request("top-headlines", {
                "country": "jp",
                "pageSize": min(page_size, 100),
            })
            articles = data.get("articles", [])
            logger.info("NewsAPI top-headlines returned %d articles", len(articles))
            # Filter to election/politics related
            political_keywords = [
                "選挙", "政治", "政党", "自民", "野党", "与党", "国会",
                "首相", "大臣", "内閣", "議員", "立憲", "維新", "共産",
            ]
            political_articles = []
            for article in articles:
                title = article.get("title", "")
                desc = article.get("description", "") or ""
                combined = title + " " + desc
                if any(kw in combined for kw in political_keywords):
                    political_articles.append(article)
            return self._normalize_articles(political_articles)
        except Exception as e:
            logger.error("Failed to fetch headlines: %s", e)
            return []

    def _normalize_articles(self, raw_articles: list[dict]) -> list[dict]:
        """Normalize NewsAPI article format to our schema.

        Filters out non-Japanese articles (Chinese, Korean, etc.)
        by checking for hiragana/katakana presence in title.
        """
        results = []
        for article in raw_articles:
            title = article.get("title", "")
            if not title or title == "[Removed]":
                continue

            description = article.get("description", "") or ""

            # Filter: require Japanese text (hiragana or katakana) in title or description
            # This excludes Chinese-only and other non-Japanese articles
            combined_text = title + " " + description
            if not _is_japanese_text(combined_text):
                continue

            source_name = article.get("source", {}).get("name", "不明")
            url = article.get("url", "")
            published_at_str = article.get("publishedAt", "")

            # Parse published date
            pub_date = None
            if published_at_str:
                try:
                    pub_date = datetime.fromisoformat(
                        published_at_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pub_date = datetime.utcnow()

            party_mention = _detect_party_mention(title, description)
            issue_category = _detect_issue_category(title, description)

            results.append({
                "source": source_name,
                "title": title,
                "url": url,
                "published_at": pub_date or datetime.utcnow(),
                "party_mention": party_mention,
                "issue_category": issue_category,
                "description": description,
            })
        return results

    async def fetch_all_data(self, days_back: int = 30) -> list[dict]:
        """Fetch all available news data.

        Combines results from multiple search strategies to maximize
        Japanese political news coverage.
        """
        from_date = datetime.utcnow() - timedelta(days=days_back)
        all_articles: list[dict] = []
        seen_urls: set[str] = set()

        def _add_unique(articles: list[dict]) -> int:
            count = 0
            for a in articles:
                url = a.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(a)
                    count += 1
            return count

        # Strategy 1: General election news (Japanese keywords)
        general = await self.fetch_election_news(
            from_date=from_date,
            page_size=100,
        )
        added = _add_unique(general)
        logger.info("Strategy 1 (general election): +%d articles", added)

        # Strategy 2: Top headlines from Japan
        headlines = await self.fetch_top_headlines(page_size=100)
        added = _add_unique(headlines)
        logger.info("Strategy 2 (top headlines): +%d articles", added)

        # Strategy 3: Per-party news
        for party_id in PARTY_KEYWORDS:
            party_articles = await self.fetch_party_news(
                party_id, days_back=days_back, max_articles=10,
            )
            added = _add_unique(party_articles)
            if added:
                logger.info("Strategy 3 (party %s): +%d articles", party_id, added)

        # Strategy 4: Broader Japanese politics search
        broader_queries = [
            "日本 政党 政策",
            "国会 法案 審議",
            "首相 内閣 政権",
        ]
        for q in broader_queries:
            extra = await self.fetch_election_news(
                query=q,
                from_date=from_date,
                page_size=50,
            )
            added = _add_unique(extra)
            if added:
                logger.info("Strategy 4 (broader '%s'): +%d articles", q, added)

        logger.info("Fetched %d total unique news articles", len(all_articles))
        return all_articles
