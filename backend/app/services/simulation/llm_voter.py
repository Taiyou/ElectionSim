"""
LLMベースのペルソナ投票エンジン

OpenRouter経由でClaude Sonnetを呼び出し、ペルソナの投票行動をLLMに判断させる。
ルールベース（vote_calculator.py）の代替として使用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from .persona_generator import Persona
from .prompts import SYSTEM_PROMPT, build_batch_prompt
from .vote_calculator import VoteDecision

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent

# .env からAPIキーを読み込む
def _load_env():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

_load_env()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "anthropic/claude-sonnet-4")


async def call_openrouter_async(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout: float = 120.0,
) -> str:
    """OpenRouter APIを非同期で呼び出す"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://election-ai.local",
        "X-Title": "Election AI Persona Simulation",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


def parse_llm_response(response_text: str, personas: list[Persona], candidates: list[dict]) -> list[VoteDecision]:
    """LLMレスポンスのJSONをパースしてVoteDecisionリストに変換"""

    # JSONブロック抽出
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # ```なしのJSONを試行
        json_str = response_text.strip()
        # 先頭/末尾の非JSON文字を除去
        start = json_str.find('[')
        end = json_str.rfind(']')
        if start >= 0 and end >= 0:
            json_str = json_str[start:end + 1]

    try:
        results = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSONパース失敗: {e}\nレスポンス先頭500文字: {response_text[:500]}")
        return []

    # 候補者名→政党IDマッピング
    candidate_party_map = {}
    party_name_to_id = {
        "自民党": "ldp", "中道改革連合": "chudo", "日本維新の会": "ishin",
        "国民民主党": "dpfp", "日本共産党": "jcp", "れいわ新選組": "reiwa",
        "参政党": "sansei", "減税日本": "genzei", "日本保守党": "hoshuto",
        "社民党": "shamin", "チームみらい": "mirai", "無所属": "independent",
        "公明党": "komei",
    }
    for c in candidates:
        candidate_party_map[c["candidate_name"]] = c.get("party_id", "independent")

    decisions = []
    for item in results:
        idx = item.get("persona_index", 0) - 1  # 1-indexed → 0-indexed
        if idx < 0 or idx >= len(personas):
            continue

        persona = personas[idx]
        will_vote = item.get("will_vote", True)

        if not will_vote:
            decisions.append(VoteDecision(
                persona_id=persona.persona_id,
                will_vote=False,
                abstention_reason=item.get("abstention_reason", "LLM判定による棄権"),
                swing_level=persona.swing_tendency,
            ))
            continue

        smd_vote = item.get("smd_vote") or {}
        prop_vote = item.get("proportional_vote") or {}

        # 候補者名から政党IDを解決
        smd_candidate = smd_vote.get("candidate", "")
        smd_party = candidate_party_map.get(smd_candidate, "")
        if not smd_party:
            # 政党名から解決を試行
            smd_party_name = smd_vote.get("party", "")
            smd_party = party_name_to_id.get(smd_party_name, smd_party_name)

        prop_party_name = prop_vote.get("party", "")
        prop_party = party_name_to_id.get(prop_party_name, prop_party_name)
        if not prop_party:
            prop_party = smd_party

        confidence = item.get("confidence", 0.5)

        decisions.append(VoteDecision(
            persona_id=persona.persona_id,
            will_vote=True,
            smd_candidate=smd_candidate,
            smd_party=smd_party,
            proportional_party=prop_party,
            confidence=confidence,
            needs_llm=False,  # LLM処理済み
            swing_level=persona.swing_tendency,
            score_breakdown={
                "method": "llm",
                "smd_reason": smd_vote.get("reason", ""),
                "proportional_reason": prop_vote.get("reason", ""),
                "swing_factors": item.get("swing_factors", []),
            },
        ))

    return decisions


async def run_llm_batch(
    district_name: str,
    area_description: str,
    candidates: list[dict],
    district_context: dict,
    personas: list[Persona],
    batch_size: int = 15,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    concurrency: int = 5,
    delay_between_batches: float = 1.0,
) -> list[VoteDecision]:
    """
    1選挙区のペルソナをバッチでLLM処理する。

    Args:
        personas: 全ペルソナリスト（100人等）
        batch_size: 1回のLLM呼び出しで処理するペルソナ数
        concurrency: 同時実行数
        delay_between_batches: バッチ間の待機秒数（レート制限対策）
    """

    all_decisions: list[VoteDecision | None] = [None] * len(personas)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_batch(batch_start: int, batch_personas: list[Persona]):
        async with semaphore:
            persona_dicts = [asdict(p) for p in batch_personas]
            prompt = build_batch_prompt(
                district_name=district_name,
                area_description=area_description,
                candidates=candidates,
                district_context=district_context,
                personas=persona_dicts,
            )

            for attempt in range(3):
                try:
                    response = await call_openrouter_async(
                        model=model,
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=prompt,
                        temperature=temperature,
                    )
                    decisions = parse_llm_response(response, batch_personas, candidates)

                    # 結果をマッピング
                    for j, decision in enumerate(decisions):
                        global_idx = batch_start + j
                        if global_idx < len(all_decisions):
                            all_decisions[global_idx] = decision

                    logger.info(
                        f"  バッチ {batch_start}-{batch_start + len(batch_personas) - 1}: "
                        f"{len(decisions)}件処理完了"
                    )
                    break
                except Exception as e:
                    logger.warning(f"  バッチ {batch_start} リトライ {attempt + 1}/3: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"  バッチ {batch_start} 失敗")

            await asyncio.sleep(delay_between_batches)

    # バッチ分割と実行
    tasks = []
    for i in range(0, len(personas), batch_size):
        batch = personas[i:i + batch_size]
        tasks.append(process_batch(i, batch))

    await asyncio.gather(*tasks)

    # Noneのままのペルソナ（LLM失敗分）はフォールバック
    final_decisions = []
    for i, decision in enumerate(all_decisions):
        if decision is None:
            # フォールバック: 棄権扱い
            final_decisions.append(VoteDecision(
                persona_id=personas[i].persona_id,
                will_vote=False,
                abstention_reason="LLM処理失敗によるフォールバック",
                swing_level=personas[i].swing_tendency,
            ))
        else:
            final_decisions.append(decision)

    return final_decisions
