from __future__ import annotations

from fastapi import APIRouter

from app.prompts.claude_integrate import (
    CLAUDE_INTEGRATION_PROMPT,
    CLAUDE_PROPORTIONAL_PROMPT,
)
from app.prompts.grok_sentiment import GROK_SENTIMENT_PROMPT
from app.prompts.perplexity_news import PERPLEXITY_PREFECTURE_PROMPT

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("")
async def get_all_prompts():
    return {
        "perplexity_news": {
            "name": "ニュース・世論調査収集プロンプト",
            "description": "Perplexity APIに送信し、各都道府県のニュース・世論調査データを収集するプロンプト",
            "template": PERPLEXITY_PREFECTURE_PROMPT,
        },
        "grok_sentiment": {
            "name": "X(Twitter)感情分析プロンプト",
            "description": "Grok APIに送信し、X上の投稿から候補者・政党への感情分析を行うプロンプト",
            "template": GROK_SENTIMENT_PROMPT,
        },
        "claude_integration": {
            "name": "統合分析プロンプト",
            "description": "Claude APIに送信し、ニュース分析とSNS分析の結果を統合して最終予測を生成するプロンプト",
            "template": CLAUDE_INTEGRATION_PROMPT,
        },
        "claude_proportional": {
            "name": "比例代表予測プロンプト",
            "description": "Claude APIに送信し、各比例ブロックの政党別議席数を予測するプロンプト",
            "template": CLAUDE_PROPORTIONAL_PROMPT,
        },
    }
