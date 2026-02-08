"""
6要因モデルによる投票先決定ロジック

ルールベースで低スイング層の投票先を決定し、
中〜高スイング層はLLMに委託するかどうかのフラグを返す。
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from .persona_generator import Persona

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
PERSONA_DIR = BASE_DIR / "persona_data"

# 投票決定要因の重み（persona_config.json と同期）
FACTOR_WEIGHTS = {
    "party_loyalty": 0.30,
    "policy_alignment": 0.25,
    "candidate_appeal": 0.20,
    "media_influence": 0.10,
    "local_connection": 0.10,
    "strategic_voting": 0.05,
}

# スイング傾向の数値変換（投票先決定の不確実性）
SWING_NOISE = {
    "very_low": 0.05,
    "low": 0.10,
    "moderate": 0.20,
    "moderate_high": 0.25,
    "high": 0.35,
    "very_high": 0.45,
}


@dataclass
class VoteDecision:
    persona_id: str
    will_vote: bool
    abstention_reason: str | None = None
    smd_candidate: str | None = None
    smd_party: str | None = None
    proportional_party: str | None = None
    confidence: float = 0.5
    needs_llm: bool = False
    swing_level: str = "low"
    score_breakdown: dict | None = None


def load_party_alignment() -> dict:
    """マニフェストデータからペルソナ-政党アライメントスコアを読み込む"""
    path = PERSONA_DIR / "manifesto_policies.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("persona_party_alignment", {})


# グローバルキャッシュ
_party_alignment_cache: dict | None = None


def get_party_alignment() -> dict:
    global _party_alignment_cache
    if _party_alignment_cache is None:
        _party_alignment_cache = load_party_alignment()
    return _party_alignment_cache


def determine_turnout(
    persona: Persona,
    weather_modifier: float = 0.0,
) -> tuple[bool, str | None]:
    """投票/棄権をルールベースで判定する（v8a Stage 1用）

    LLMの投票率過大予測を回避するため、投票率の判定はルールベースで行い、
    投票先の選択のみをLLMに委ねるデカップリング方式の第1段階。

    Args:
        persona: 対象ペルソナ
        weather_modifier: 天候による投票率補正（負の値で低下、例: -0.10）

    Returns:
        (will_vote, abstention_reason) のタプル
    """
    adjusted_prob = persona.turnout_probability + weather_modifier
    adjusted_prob = max(0.05, min(0.95, adjusted_prob))

    will_vote = random.random() < adjusted_prob
    if not will_vote:
        reason = _generate_abstention_reason(persona)
        return False, reason
    return True, None


def calculate_vote(
    persona: Persona,
    candidates: list[dict],
    district_data: dict,
    factor_weights: dict | None = None,
    swing_noise_offset: float = 0.0,
    independent_loyalty_score: float = 0.3,
) -> VoteDecision:
    """
    ペルソナの投票行動を算出する。

    低スイング層: ルールベースで確定的に投票先を決定
    中〜高スイング層: needs_llm=True を返し、LLMに委託
    """

    # 1. 投票/棄権判定
    will_vote = random.random() < persona.turnout_probability
    if not will_vote:
        reason = _generate_abstention_reason(persona)
        return VoteDecision(
            persona_id=persona.persona_id,
            will_vote=False,
            abstention_reason=reason,
            swing_level=persona.swing_tendency,
        )

    # 使用する重みの決定
    weights = factor_weights if factor_weights is not None else FACTOR_WEIGHTS

    # 2. スイングレベル判定
    swing_level = persona.swing_tendency
    needs_llm = swing_level in ("moderate", "moderate_high", "high", "very_high")

    # 3. 各候補者のスコア算出
    alignment = get_party_alignment()
    archetype_alignment = alignment.get(persona.archetype_id, {})

    candidate_scores = {}
    for candidate in candidates:
        party_id = candidate.get("party_id", "independent")
        score = _calculate_candidate_score(
            persona, candidate, party_id, archetype_alignment, district_data,
            weights=weights, independent_loyalty_score=independent_loyalty_score,
        )
        candidate_scores[candidate["candidate_name"]] = {
            "score": score,
            "party_id": party_id,
        }

    if not candidate_scores:
        return VoteDecision(
            persona_id=persona.persona_id, will_vote=True,
            smd_candidate="白票", confidence=0.0,
            needs_llm=False, swing_level=swing_level,
        )

    # 4. スコアにノイズを加えてランダム性を付与
    noise_level = SWING_NOISE.get(swing_level, 0.20) + swing_noise_offset
    noisy_scores = {}
    for name, data in candidate_scores.items():
        noise = random.gauss(0, noise_level)
        noisy_scores[name] = data["score"] + noise

    # 5. 最高スコアの候補者を選択
    winner = max(noisy_scores, key=noisy_scores.get)
    winner_party = candidate_scores[winner]["party_id"]

    # 6. 確信度算出（1位と2位の差）
    sorted_scores = sorted(noisy_scores.values(), reverse=True)
    if len(sorted_scores) >= 2:
        confidence = min(1.0, max(0.1, (sorted_scores[0] - sorted_scores[1]) * 2))
    else:
        confidence = 0.8

    # 7. 比例投票先（小選挙区と同じ政党 or 支持政党に基づく）
    proportional_party = _decide_proportional_vote(
        persona, winner_party, archetype_alignment, noise_level
    )

    return VoteDecision(
        persona_id=persona.persona_id,
        will_vote=True,
        smd_candidate=winner,
        smd_party=winner_party,
        proportional_party=proportional_party,
        confidence=round(confidence, 3),
        needs_llm=needs_llm,
        swing_level=swing_level,
        score_breakdown=candidate_scores,
    )


def _calculate_candidate_score(
    persona: Persona,
    candidate: dict,
    party_id: str,
    archetype_alignment: dict,
    district_data: dict,
    weights: dict | None = None,
    independent_loyalty_score: float = 0.3,
) -> float:
    """6要因モデルで候補者スコアを算出"""

    if weights is None:
        weights = FACTOR_WEIGHTS

    # Factor 1: 政党忠誠度
    party_loyalty_score = 0.0
    party_name_map = {
        "ldp": "自民", "chudo": "中道", "ishin": "維新", "dpfp": "国民民主",
        "jcp": "共産", "reiwa": "れいわ", "sansei": "参政", "genzei": "減税",
        "hoshuto": "保守", "shamin": "社民", "mirai": "みらい",
    }
    if persona.party_affinity == party_id or persona.party_affinity == party_name_map.get(party_id, ""):
        party_loyalty_score = 1.0
    elif persona.party_affinity == "支持なし":
        party_loyalty_score = independent_loyalty_score  # 無党派: オーバーライド可能
    else:
        party_loyalty_score = 0.1  # 他党支持者

    # Factor 2: 政策アライメント
    policy_score = archetype_alignment.get(party_id, 0.3)

    # Factor 3: 候補者個人の魅力（現職・当選回数ボーナス）
    candidate_score = 0.3  # ベース
    status = candidate.get("status", "new")
    prev_wins = int(candidate.get("previous_wins", 0))
    if status == "incumbent":
        candidate_score += 0.3
    elif status == "former":
        candidate_score += 0.15
    candidate_score += min(0.2, prev_wins * 0.05)  # 当選回数ボーナス（上限0.2）

    # Factor 4: メディア影響（政党の支持率を代理変数に）
    media_score = float(district_data.get("支持率_自民党" if party_id == "ldp" else "支持率_その他", 0.1))

    # Factor 5: 地域つながり
    local_score = 0.3  # ベース
    if status == "incumbent":
        local_score += 0.3  # 現職は地元つながりが強い

    # Factor 6: 戦略的投票（当選可能性）
    strategic_score = 0.5  # ベース
    if status == "incumbent":
        strategic_score += 0.2
    if candidate.get("dual_candidacy") == "true":
        strategic_score -= 0.1  # 比例復活の可能性あり = 戦略的価値やや低

    # 加重合算
    total = (
        weights["party_loyalty"] * party_loyalty_score
        + weights["policy_alignment"] * policy_score
        + weights["candidate_appeal"] * candidate_score
        + weights["media_influence"] * media_score
        + weights["local_connection"] * local_score
        + weights["strategic_voting"] * strategic_score
    )

    return total


def _decide_proportional_vote(
    persona: Persona,
    smd_party: str,
    archetype_alignment: dict,
    noise_level: float,
) -> str:
    """比例投票先を決定（票割れの可能性あり）"""

    # 基本: 小選挙区と同じ政党
    split_ticket_prob = noise_level * 0.5  # スイング度が高いほど票割れしやすい

    if random.random() < split_ticket_prob:
        # 票割れ: アライメントスコアに基づいて別の政党を選択
        party_scores = {p: s + random.gauss(0, 0.1) for p, s in archetype_alignment.items()}
        if party_scores:
            return max(party_scores, key=party_scores.get)

    return smd_party


def _generate_abstention_reason(persona: Persona) -> str:
    """棄権理由を生成"""
    reasons_by_engagement = {
        "low": [
            "政治に関心がない",
            "誰に投票しても変わらないと思う",
            "仕事・予定があり投票に行けない",
            "投票所が遠い",
            "支持する候補者がいない",
        ],
        "moderate": [
            "天候が悪く外出を控えた",
            "支持する候補者がいない",
            "期日前投票を忘れた",
            "体調不良",
        ],
        "high": [
            "体調不良で外出できない",
            "大雪で投票所に行けない",
            "急用が入った",
        ],
    }

    engagement = persona.political_engagement
    if engagement in ("moderate_high",):
        engagement = "moderate"

    reasons = reasons_by_engagement.get(engagement, reasons_by_engagement["moderate"])
    return random.choice(reasons)
