from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/personas", tags=["personas"])

PERSONA_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "persona_data"


@lru_cache(maxsize=1)
def _load_json(filename: str) -> dict | list:
    path = PERSONA_DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Persona data file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_config():
    return _load_json("persona_config.json")


def _load_demographics():
    return _load_json("prefecture_demographics.json")


def _load_socioeconomic():
    return _load_json("socioeconomic_indicators.json")


def _load_political():
    return _load_json("political_tendencies.json")


def _load_regional_issues():
    return _load_json("regional_issues.json")


def _load_voter_profiles():
    return _load_json("voter_profiles.json")


@router.get("/summary")
async def get_persona_summary():
    config = _load_config()
    voter_profiles = _load_voter_profiles()
    regional_issues = _load_regional_issues()
    political = _load_political()

    archetypes = config["persona_archetypes"]

    # Build archetype info list
    archetype_list = []
    for a in archetypes:
        archetype_list.append({
            "id": a["id"],
            "name_ja": a["name_ja"],
            "age_range": a["age_range"],
            "turnout_probability": a["voting_behavior"]["turnout_probability"],
            "swing_tendency": a["voting_behavior"]["swing_tendency"],
            "typical_concerns": a["typical_concerns"],
        })

    # Average turnout probability across archetypes
    avg_turnout = sum(
        a["voting_behavior"]["turnout_probability"] for a in archetypes
    ) / len(archetypes)

    # National average archetype distribution
    national_dist: dict[str, float] = {}
    for profile in voter_profiles:
        for archetype_id, ratio in profile["archetype_distribution"].items():
            national_dist[archetype_id] = national_dist.get(archetype_id, 0.0) + ratio
    n_prefs = len(voter_profiles)
    national_dist = {k: round(v / n_prefs, 4) for k, v in national_dist.items()}

    # Top regional issues (aggregated across all prefectures)
    issue_counter: Counter = Counter()
    issue_priority_sum: dict[str, float] = {}
    prefectures_data = regional_issues.get("prefectures", regional_issues)
    if isinstance(prefectures_data, dict):
        prefectures_data = prefectures_data.get("prefectures", [])
    for pref in prefectures_data:
        for issue_item in pref.get("primary_issues", []):
            name = issue_item["issue"]
            issue_counter[name] += 1
            issue_priority_sum[name] = issue_priority_sum.get(name, 0.0) + issue_item.get("priority", 0)

    top_issues = []
    for issue_name, count in issue_counter.most_common(15):
        top_issues.append({
            "issue": issue_name,
            "count": count,
            "priority_avg": round(issue_priority_sum[issue_name] / count, 3),
        })

    # Voting decision factors
    voting_factors = []
    for name, info in config["voting_decision_factors"].items():
        voting_factors.append({
            "name": name,
            "weight": info["weight"],
            "description": info["description"],
        })

    # Average swing voter ratio
    political_prefs = political.get("prefectures", political)
    if isinstance(political_prefs, dict):
        political_prefs = political_prefs.get("prefectures", [])
    avg_swing = sum(
        p.get("swing_voter_ratio", 0) for p in political_prefs
    ) / max(len(political_prefs), 1)

    return {
        "total_prefectures": n_prefs,
        "total_archetypes": len(archetypes),
        "avg_turnout_probability": round(avg_turnout, 3),
        "avg_swing_voter_ratio": round(avg_swing, 3),
        "archetypes": archetype_list,
        "national_archetype_distribution": national_dist,
        "top_regional_issues": top_issues,
        "voting_factors": voting_factors,
    }


@router.get("/demographics")
async def get_demographics():
    data = _load_demographics()
    return data


@router.get("/political")
async def get_political_tendencies():
    data = _load_political()
    return data


@router.get("/prefecture/{code}")
async def get_prefecture_detail(code: int):
    demographics = _load_demographics()
    socioeconomic = _load_socioeconomic()
    political = _load_political()
    regional_issues = _load_regional_issues()
    voter_profiles = _load_voter_profiles()

    def find_by_code(data, code: int):
        items = data if isinstance(data, list) else data.get("prefectures", [])
        for item in items:
            if item.get("prefecture_code") == code:
                return item
        return None

    demo = find_by_code(demographics, code)
    if not demo:
        raise HTTPException(status_code=404, detail=f"Prefecture code {code} not found")

    return {
        "demographics": demo,
        "socioeconomic": find_by_code(socioeconomic, code),
        "political": find_by_code(political, code),
        "regional_issues": find_by_code(regional_issues, code),
        "voter_profile": find_by_code(voter_profiles, code),
    }
