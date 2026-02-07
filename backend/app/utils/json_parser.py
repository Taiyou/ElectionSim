from __future__ import annotations

import json
import re

from app.utils.logger import get_logger

logger = get_logger(__name__)


def strip_markdown_json(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from AI responses."""
    pattern = r"```(?:json)?\s*\n?(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        return "\n".join(lines).strip()
    return stripped


def parse_ai_json_response(content: str, context: str = "") -> dict:
    """Parse JSON from AI response, handling markdown fences and malformed output.

    Args:
        content: Raw AI response text.
        context: Description for log messages (e.g. "Claude/東京都").

    Returns:
        Parsed dict, or a fallback dict with ``raw_response`` on failure.
    """
    cleaned = strip_markdown_json(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Non-JSON response from %s, attempting secondary cleanup", context)
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        logger.error("Could not parse JSON response from %s", context)
        return {"raw_response": content}
