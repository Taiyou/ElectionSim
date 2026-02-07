"""
シミュレーション結果の集計

100ペルソナの投票結果を選挙区レベルに集計する。
"""

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

    # アーキタイプ別投票内訳
    archetype_breakdown: dict[str, dict] = {}
    for persona, decision in zip(personas, decisions):
        arch = persona.archetype_id
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
