from __future__ import annotations

import csv
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/manifesto", tags=["manifesto"])

PERSONA_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "persona_data"


@lru_cache(maxsize=1)
def _load_manifesto():
    path = PERSONA_DATA_DIR / "manifesto_policies.json"
    if not path.exists():
        raise FileNotFoundError(f"Manifesto data file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_manifesto_links() -> list[dict]:
    path = PERSONA_DATA_DIR / "manifesto_links.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


@router.get("/summary")
async def get_manifesto_summary():
    data = _load_manifesto()

    metadata = data["metadata"]
    parties_data = data["parties"]
    alignment = data["persona_party_alignment"]
    persona_names = data["persona_names"]
    issue_categories = metadata["issue_categories"]
    party_names = metadata["party_names"]

    # Build party responses with name
    parties = []
    total_policies = 0
    for party in parties_data:
        pid = party["party_id"]
        policies = party["policies"]
        total_policies += len(policies)
        parties.append({
            "party_id": pid,
            "party_name": party_names.get(pid, pid),
            "policies": policies,
        })

    # Issue category breakdown
    category_policy_count: dict[str, int] = defaultdict(int)
    category_high_priority_parties: dict[str, set] = defaultdict(set)
    for party in parties_data:
        for policy in party["policies"]:
            cat = policy["category"]
            category_policy_count[cat] += 1
            if policy["priority"] == "high":
                category_high_priority_parties[cat].add(party["party_id"])

    issue_breakdown = []
    for cat, cat_name in issue_categories.items():
        issue_breakdown.append({
            "category": cat,
            "category_name": cat_name,
            "party_count": len(category_high_priority_parties.get(cat, set())),
            "total_policies": category_policy_count.get(cat, 0),
        })

    # Policy comparison matrix: category -> party_id -> title
    comparison_matrix: dict[str, dict[str, str]] = {}
    for cat in issue_categories:
        comparison_matrix[cat] = {}
    for party in parties_data:
        for policy in party["policies"]:
            comparison_matrix[policy["category"]][party["party_id"]] = policy["title"]

    # ── Overview insights ──

    # 1. Most contested category (most parties have high-priority policy)
    most_contested = max(issue_breakdown, key=lambda x: x["party_count"])

    # 2. Least covered category
    least_covered = min(issue_breakdown, key=lambda x: x["total_policies"])

    # 3. For each persona, find the best-matching party
    persona_best_party: list[dict] = []
    for persona_id, scores in alignment.items():
        best_pid = max(scores, key=scores.get)
        persona_best_party.append({
            "persona_id": persona_id,
            "persona_name": persona_names.get(persona_id, persona_id),
            "best_party_id": best_pid,
            "best_party_name": party_names.get(best_pid, best_pid),
            "score": scores[best_pid],
        })

    # 4. Policy focus classification per party
    #    conservative = national_security / constitutional_reform heavy
    #    progressive  = social_security / environment / education heavy
    #    economic     = economy heavy
    party_focus: list[dict] = []
    progressive_cats = {"social_security", "education", "environment"}
    conservative_cats = {"national_security", "constitutional_reform"}
    for party in parties_data:
        pid = party["party_id"]
        high_cats = [p["category"] for p in party["policies"] if p["priority"] == "high"]
        prog_count = sum(1 for c in high_cats if c in progressive_cats)
        cons_count = sum(1 for c in high_cats if c in conservative_cats)
        econ_count = sum(1 for c in high_cats if c == "economy")

        if prog_count > cons_count and prog_count >= econ_count:
            focus_type = "progressive"
            focus_label = "生活・社会保障重視"
        elif cons_count > prog_count:
            focus_type = "conservative"
            focus_label = "安全保障・体制改革重視"
        elif econ_count >= prog_count and econ_count >= cons_count:
            focus_type = "economic"
            focus_label = "経済・成長重視"
        else:
            focus_type = "balanced"
            focus_label = "バランス型"

        party_focus.append({
            "party_id": pid,
            "party_name": party_names.get(pid, pid),
            "focus_type": focus_type,
            "focus_label": focus_label,
            "high_priority_count": len(high_cats),
            "total_policy_count": len(party["policies"]),
        })

    # 5. Persona coverage — how many parties target each persona
    persona_coverage: dict[str, int] = defaultdict(int)
    for party in parties_data:
        targeted_personas: set[str] = set()
        for policy in party["policies"]:
            for pid in policy["target_personas"]:
                targeted_personas.add(pid)
        for pid in targeted_personas:
            persona_coverage[pid] += 1

    most_targeted_persona_id = max(persona_coverage, key=persona_coverage.get)
    least_targeted_persona_id = min(persona_coverage, key=persona_coverage.get)

    # 6. Political spectrum grouping
    spectrum_groups = {
        "conservative": [],
        "progressive": [],
        "economic": [],
        "balanced": [],
    }
    for pf in party_focus:
        spectrum_groups[pf["focus_type"]].append(pf["party_name"])

    overview = {
        "most_contested_category": {
            "category": most_contested["category"],
            "category_name": most_contested["category_name"],
            "party_count": most_contested["party_count"],
        },
        "least_covered_category": {
            "category": least_covered["category"],
            "category_name": least_covered["category_name"],
            "total_policies": least_covered["total_policies"],
        },
        "persona_best_party": persona_best_party,
        "party_focus": party_focus,
        "spectrum_groups": spectrum_groups,
        "persona_coverage": {
            "most_targeted": {
                "persona_id": most_targeted_persona_id,
                "persona_name": persona_names.get(most_targeted_persona_id, most_targeted_persona_id),
                "party_count": persona_coverage[most_targeted_persona_id],
            },
            "least_targeted": {
                "persona_id": least_targeted_persona_id,
                "persona_name": persona_names.get(least_targeted_persona_id, least_targeted_persona_id),
                "party_count": persona_coverage[least_targeted_persona_id],
            },
        },
    }

    # Load manifesto links from CSV
    manifesto_links = _load_manifesto_links()

    return {
        "total_parties": len(parties_data),
        "total_categories": len(issue_categories),
        "total_policies": total_policies,
        "parties": parties,
        "persona_party_alignment": alignment,
        "persona_names": persona_names,
        "issue_category_breakdown": issue_breakdown,
        "policy_comparison_matrix": comparison_matrix,
        "overview": overview,
        "manifesto_links": manifesto_links,
    }
