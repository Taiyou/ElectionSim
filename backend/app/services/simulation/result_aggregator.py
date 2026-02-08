"""
シミュレーション結果の集計

100ペルソナの投票結果を選挙区レベルに集計する。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from .persona_generator import Persona
from .vote_calculator import VoteDecision


@dataclass
class DistrictResult:
    district_id: str
    district_name: str
    total_personas: int
    turnout_count: int
    turnout_rate: float

    # 小選挙区結果
    winner: str
    winner_party: str
    winner_votes: int
    runner_up: str
    runner_up_party: str
    runner_up_votes: int
    margin: int
    smd_votes: dict[str, int] = field(default_factory=dict)  # candidate -> votes

    # 比例代表結果
    proportional_votes: dict[str, int] = field(default_factory=dict)  # party -> votes

    # アーキタイプ別投票内訳
    archetype_breakdown: dict[str, dict] = field(default_factory=dict)

    # 棄権理由
    abstention_reasons: list[str] = field(default_factory=list)


def aggregate_district_results(
    district_id: str,
    district_name: str,
    personas: list[Persona],
    decisions: list[VoteDecision],
    candidates: list[dict],
) -> DistrictResult:
    """ペルソナの投票決定を選挙区レベルに集計"""

    total = len(decisions)
    voted = [d for d in decisions if d.will_vote]
    turnout_count = len(voted)
    turnout_rate = round(turnout_count / total, 4) if total > 0 else 0

    # 小選挙区集計
    smd_votes: dict[str, int] = {}
    smd_party_map: dict[str, str] = {}
    for d in voted:
        if d.smd_candidate and d.smd_candidate != "白票":
            smd_votes[d.smd_candidate] = smd_votes.get(d.smd_candidate, 0) + 1
            if d.smd_party:
                smd_party_map[d.smd_candidate] = d.smd_party

    # 候補者名がない場合は政党名で集計
    if not smd_votes:
        for d in voted:
            if d.smd_party:
                # 候補者名を政党から推定
                for c in candidates:
                    if c.get("party_id") == d.smd_party:
                        name = c["candidate_name"]
                        smd_votes[name] = smd_votes.get(name, 0) + 1
                        smd_party_map[name] = d.smd_party
                        break

    # 得票順にソート
    sorted_candidates = sorted(smd_votes.items(), key=lambda x: -x[1])

    winner = sorted_candidates[0][0] if sorted_candidates else ""
    winner_party = smd_party_map.get(winner, "")
    winner_votes = sorted_candidates[0][1] if sorted_candidates else 0

    runner_up = sorted_candidates[1][0] if len(sorted_candidates) > 1 else ""
    runner_up_party = smd_party_map.get(runner_up, "")
    runner_up_votes = sorted_candidates[1][1] if len(sorted_candidates) > 1 else 0

    margin = winner_votes - runner_up_votes

    # 比例代表集計
    proportional_votes: dict[str, int] = {}
    for d in voted:
        if d.proportional_party:
            proportional_votes[d.proportional_party] = (
                proportional_votes.get(d.proportional_party, 0) + 1
            )

    # アーキタイプ別（または属性別）投票内訳
    archetype_breakdown: dict[str, dict] = {}
    for persona, decision in zip(personas, decisions):
        arch = getattr(persona, "archetype_id", getattr(persona, "industry_sector", "unknown"))
        if arch not in archetype_breakdown:
            archetype_breakdown[arch] = {
                "count": 0, "voted": 0, "smd_parties": {}, "proportional_parties": {}
            }
        archetype_breakdown[arch]["count"] += 1
        if decision.will_vote:
            archetype_breakdown[arch]["voted"] += 1
            if decision.smd_party:
                p = decision.smd_party
                archetype_breakdown[arch]["smd_parties"][p] = (
                    archetype_breakdown[arch]["smd_parties"].get(p, 0) + 1
                )
            if decision.proportional_party:
                p = decision.proportional_party
                archetype_breakdown[arch]["proportional_parties"][p] = (
                    archetype_breakdown[arch]["proportional_parties"].get(p, 0) + 1
                )

    # 棄権理由
    abstention_reasons = [
        d.abstention_reason for d in decisions
        if not d.will_vote and d.abstention_reason
    ]

    return DistrictResult(
        district_id=district_id,
        district_name=district_name,
        total_personas=total,
        turnout_count=turnout_count,
        turnout_rate=turnout_rate,
        winner=winner,
        winner_party=winner_party,
        winner_votes=winner_votes,
        runner_up=runner_up,
        runner_up_party=runner_up_party,
        runner_up_votes=runner_up_votes,
        margin=margin,
        smd_votes=dict(smd_votes),
        proportional_votes=proportional_votes,
        archetype_breakdown=archetype_breakdown,
        abstention_reasons=abstention_reasons,
    )


def calibrate_decisions(
    decisions: list[VoteDecision],
    district_context: dict,
    strength: float = 0.3,
    seed: int | None = None,
) -> list[VoteDecision]:
    """事後キャリブレーション: LLM出力の政党分布を選挙区支持率分布に向けてソフトに補正する

    Argyle et al. (2023) "Out of One, Many" の raking 手法を簡易化したアプローチ。
    LLMの出力をそのまま使うのではなく、選挙区の過去の支持率分布をアンカーとして
    一定の割合で補正を行う。

    Args:
        decisions: LLMが出力した投票決定リスト
        district_context: 選挙区コンテキスト（支持率データを含む）
        strength: キャリブレーション強度（0.0=補正なし、1.0=完全に支持率分布に合わせる）
        seed: 乱数シード

    Returns:
        補正済みのVoteDecisionリスト
    """
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    # 選挙区の目標支持率分布を取得
    target_distribution: dict[str, float] = {}
    support_keys = [
        ("支持率_自民党", "ldp"),
        ("支持率_立憲民主党", "chudo"),
        ("支持率_維新", "ishin"),
        ("支持率_国民民主党", "dpfp"),
        ("支持率_共産党", "jcp"),
        ("支持率_れいわ", "reiwa"),
        ("支持率_参政党", "sansei"),
        ("支持率_その他", "other"),
    ]
    for key, party_id in support_keys:
        val = float(district_context.get(key, 0))
        if val > 0:
            target_distribution[party_id] = val

    if not target_distribution:
        return decisions

    # 現在のLLM出力の政党分布を集計
    voted = [d for d in decisions if d.will_vote and d.smd_party]
    if not voted:
        return decisions

    current_counts: dict[str, int] = {}
    for d in voted:
        current_counts[d.smd_party] = current_counts.get(d.smd_party, 0) + 1

    total_voted = len(voted)

    # 各政党の現在割合と目標割合の差分を計算
    current_distribution: dict[str, float] = {
        p: c / total_voted for p, c in current_counts.items()
    }

    # 目標分布を正規化
    target_total = sum(target_distribution.values())
    if target_total > 0:
        target_distribution = {p: v / target_total for p, v in target_distribution.items()}

    # 過剰な政党から不足している政党への票の移動確率を計算
    over_represented: dict[str, float] = {}
    under_represented: dict[str, float] = {}

    for party in set(list(current_distribution.keys()) + list(target_distribution.keys())):
        current = current_distribution.get(party, 0)
        target = target_distribution.get(party, 0)
        diff = current - target
        if diff > 0.01:  # 1%以上過剰
            over_represented[party] = diff * strength
        elif diff < -0.01:  # 1%以上不足
            under_represented[party] = abs(diff) * strength

    if not over_represented or not under_represented:
        return decisions

    # 過剰政党のペルソナを確率的に不足政党に再割当て
    calibrated = list(decisions)
    under_parties = list(under_represented.keys())
    under_weights = [under_represented[p] for p in under_parties]

    for i, d in enumerate(calibrated):
        if not d.will_vote or not d.smd_party:
            continue
        if d.smd_party not in over_represented:
            continue

        flip_prob = over_represented[d.smd_party]
        if rng.random() < flip_prob:
            # 不足政党に再割当て（重み付きランダム選択）
            total_w = sum(under_weights)
            if total_w <= 0:
                continue
            r = rng.random() * total_w
            cumulative = 0
            new_party = under_parties[0]
            for p, w in zip(under_parties, under_weights):
                cumulative += w
                if r <= cumulative:
                    new_party = p
                    break

            calibrated[i] = VoteDecision(
                persona_id=d.persona_id,
                will_vote=True,
                smd_candidate=d.smd_candidate,
                smd_party=new_party,
                proportional_party=d.proportional_party,
                confidence=d.confidence * 0.8,  # 補正された票は確信度を下げる
                needs_llm=d.needs_llm,
                swing_level=d.swing_level,
                score_breakdown=d.score_breakdown,
            )

    return calibrated


def compute_calibration_signals(
    decisions: list[VoteDecision],
    district_context: dict,
) -> list[dict]:
    """LLM予測と選挙区支持率分布の乖離をキャリブレーション信号として算出する

    Returns:
        各政党の {"party_id", "target_share", "predicted_share", "correction"} のリスト
    """
    support_keys = [
        ("支持率_自民党", "ldp"),
        ("支持率_立憲民主党", "chudo"),
        ("支持率_維新", "ishin"),
        ("支持率_国民民主党", "dpfp"),
        ("支持率_共産党", "jcp"),
        ("支持率_れいわ", "reiwa"),
        ("支持率_参政党", "sansei"),
        ("支持率_その他", "other"),
    ]

    target_distribution: dict[str, float] = {}
    for key, party_id in support_keys:
        val = float(district_context.get(key, 0))
        if val > 0:
            target_distribution[party_id] = val

    if not target_distribution:
        return []

    # 目標分布を正規化
    target_total = sum(target_distribution.values())
    if target_total > 0:
        target_distribution = {p: v / target_total for p, v in target_distribution.items()}

    # LLM出力の政党分布を集計
    voted = [d for d in decisions if d.will_vote and d.smd_party]
    if not voted:
        return []

    current_counts: dict[str, int] = {}
    for d in voted:
        current_counts[d.smd_party] = current_counts.get(d.smd_party, 0) + 1

    total_voted = len(voted)
    predicted_distribution: dict[str, float] = {
        p: c / total_voted for p, c in current_counts.items()
    }

    # 各政党の信号を算出
    signals = []
    all_parties = set(list(target_distribution.keys()) + list(predicted_distribution.keys()))
    for party_id in all_parties:
        target = target_distribution.get(party_id, 0.0)
        predicted = predicted_distribution.get(party_id, 0.0)
        signals.append({
            "party_id": party_id,
            "target_share": round(target, 4),
            "predicted_share": round(predicted, 4),
            "correction": round(target - predicted, 4),
        })

    return signals
