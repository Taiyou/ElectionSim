from __future__ import annotations

from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.prompts.grok_sentiment import GROK_SENTIMENT_PROMPT
from app.services.openrouter_client import call_openrouter
from app.utils.json_parser import parse_ai_json_response
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _format_districts(districts: list[dict]) -> str:
    lines: list[str] = []
    for d in districts:
        lines.append(f"\n■ {d['name']} ({d['id']})")
        lines.append("  候補者:")
        for c in d.get("candidates", []):
            incumbent = "（現職）" if c.get("is_incumbent") else ""
            lines.append(f"    - {c['name']}（{c['party_id']}）{incumbent}")
    return "\n".join(lines)


class GrokService:
    """Grok (x-ai) via OpenRouter for X/Twitter sentiment analysis."""

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def analyze_prefecture(
        self, prefecture: str, districts: list[dict]
    ) -> dict:
        today = date.today().isoformat()
        prompt = GROK_SENTIMENT_PROMPT.format(
            today=today,
            prefecture=prefecture,
            districts_and_candidates=_format_districts(districts),
        )

        content = await call_openrouter(settings.GROK_MODEL, prompt)
        return parse_ai_json_response(content, context=f"Grok/{prefecture}")
