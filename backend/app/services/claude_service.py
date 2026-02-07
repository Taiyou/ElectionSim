from __future__ import annotations

import json
from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.prompts.claude_integrate import (
    CLAUDE_INTEGRATION_PROMPT,
    CLAUDE_PROPORTIONAL_PROMPT,
)
from app.services.openrouter_client import call_openrouter
from app.utils.json_parser import parse_ai_json_response
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _format_master_data(districts: list[dict]) -> str:
    lines: list[str] = []
    for d in districts:
        lines.append(f"\n■ {d['name']} ({d['id']})")
        lines.append(f"  エリア: {d['area_description']}")
        lines.append("  候補者:")
        for c in d.get("candidates", []):
            incumbent = "現職" if c.get("is_incumbent") else "新人"
            wins = f"当選{c['previous_wins']}回" if c.get("previous_wins") else ""
            lines.append(
                f"    - {c['name']}（{c['party_id']}・{incumbent}）{wins}"
            )
    return "\n".join(lines)


class ClaudeService:
    """Claude (Anthropic) via OpenRouter for integration analysis."""

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def integrate_and_predict(
        self,
        prefecture: str,
        districts: list[dict],
        perplexity_result: dict,
        grok_result: dict,
    ) -> dict:
        today = date.today().isoformat()
        prompt = CLAUDE_INTEGRATION_PROMPT.format(
            today=today,
            prefecture=prefecture,
            master_data=_format_master_data(districts),
            perplexity_result=json.dumps(perplexity_result, ensure_ascii=False, indent=2),
            grok_result=json.dumps(grok_result, ensure_ascii=False, indent=2),
        )

        max_tokens = max(4096, len(districts) * 600 + 1024)
        content = await call_openrouter(
            settings.CLAUDE_MODEL, prompt, max_tokens=max_tokens
        )
        return parse_ai_json_response(content, context=f"Claude/{prefecture}")

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def predict_proportional(
        self,
        block_id: str,
        block_name: str,
        total_seats: int,
        prefectures: list[str],
        district_predictions: list[dict],
        parties_data: list[dict],
    ) -> dict:
        today = date.today().isoformat()
        prompt = CLAUDE_PROPORTIONAL_PROMPT.format(
            today=today,
            block_id=block_id,
            block_name=block_name,
            total_seats=total_seats,
            prefectures="、".join(prefectures),
            district_predictions=json.dumps(
                district_predictions, ensure_ascii=False, indent=2
            ),
            parties_data=json.dumps(parties_data, ensure_ascii=False, indent=2),
        )

        content = await call_openrouter(settings.CLAUDE_MODEL, prompt)
        return parse_ai_json_response(content, context=f"Claude/proportional/{block_id}")
