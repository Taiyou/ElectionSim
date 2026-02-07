from __future__ import annotations

import httpx

from app.config import settings
from app.utils.logger import get_logger
from app.utils.rate_limiter import AsyncRateLimiter

logger = get_logger(__name__)

# Shared rate limiter across all services to respect a single API key limit.
_shared_rate_limiter = AsyncRateLimiter(settings.API_RATE_LIMIT_PER_MINUTE)

_HEADERS = {
    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://election-ai.local",
    "X-Title": "Election AI Prediction System",
}

_API_URL = f"{settings.OPENROUTER_BASE_URL}/chat/completions"


async def call_openrouter(
    model: str,
    prompt: str,
    *,
    max_tokens: int = 4096,
    timeout: float = 120.0,
) -> str:
    """Send a chat completion request to OpenRouter and return the content string.

    Handles rate-limiting transparently.
    """
    await _shared_rate_limiter.acquire()

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            _API_URL,
            headers=_HEADERS,
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]
