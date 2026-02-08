"""
v3 本実験: 異なる条件での3シナリオ比較実験

v2（ルールベース・デフォルト重み）との比較を目的に、
投票決定要因の重みを変えた3つのシナリオで全289選挙区を実行する。

シナリオ:
  A: 政策重視モデル — 政策アライメント↑、政党忠誠度↓
  B: 政権交代風モデル — 無党派層が野党寄り、スイング大
  C: 高投票率モデル — 投票率ブースト、無党派層増加

使い方:
  python scripts/run_v3_experiments.py              # 全3シナリオ実行
  python scripts/run_v3_experiments.py --scenario A # シナリオA のみ
  python scripts/run_v3_experiments.py --scenario B --seeds 42 99
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.simulation.engine import SimulationEngine
from backend.app.services.simulation.vote_calculator import FACTOR_WEIGHTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# シナリオ定義
# ──────────────────────────────────────────────

SCENARIOS = {
    "A": {
        "name": "v3a_policy_focused",
        "description": "政策重視モデル: policy_alignment↑(0.35), party_loyalty↓(0.20)",
        "hypothesis": "政策アライメントの重みを上げ、政党忠誠度を下げると野党が議席増",
        "factor_weights": {
            "party_loyalty": 0.20,
            "policy_alignment": 0.35,
            "candidate_appeal": 0.20,
            "media_influence": 0.12,
            "local_connection": 0.08,
            "strategic_voting": 0.05,
        },
        "swing_noise_offset": 0.0,
        "independent_loyalty_score": 0.3,
        "turnout_boost": 0.0,
        "tags": ["v3", "v3a_policy_focused", "v1_rule_based"],
    },
    "B": {
        "name": "v3b_anti_establishment",
        "description": "政権交代風モデル: party_loyalty↓(0.15), swing↑(+0.05), 無党派忠誠度↓(0.15)",
        "hypothesis": "無党派層が野党寄りに動き、スイングが大きくなるシナリオ",
        "factor_weights": {
            "party_loyalty": 0.15,
            "policy_alignment": 0.30,
            "candidate_appeal": 0.25,
            "media_influence": 0.15,
            "local_connection": 0.08,
            "strategic_voting": 0.07,
        },
        "swing_noise_offset": 0.05,
        "independent_loyalty_score": 0.15,
        "turnout_boost": 0.0,
        "tags": ["v3", "v3b_anti_establishment", "v1_rule_based"],
    },
    "C": {
        "name": "v3c_high_turnout",
        "description": "高投票率モデル: 投票率+8%, party_loyalty↓(0.22), policy↑(0.30)",
        "hypothesis": "投票率が上がると浮動票が増え、野党有利になる",
        "factor_weights": {
            "party_loyalty": 0.22,
            "policy_alignment": 0.30,
            "candidate_appeal": 0.20,
            "media_influence": 0.13,
            "local_connection": 0.08,
            "strategic_voting": 0.07,
        },
        "swing_noise_offset": 0.0,
        "independent_loyalty_score": 0.25,
        "turnout_boost": 0.08,
        "tags": ["v3", "v3c_high_turnout", "v1_rule_based"],
    },
}

DEFAULT_SEEDS = [42, 99, 123]


def print_weight_comparison(scenario: dict):
    """v2デフォルトとの重み比較を表示"""
    print(f"\n  {'要因':<22s} {'v2':>6s} {'v3':>6s} {'差分':>8s}")
    print(f"  {'─'*44}")
    for key in FACTOR_WEIGHTS:
        v2_val = FACTOR_WEIGHTS[key]
        v3_val = scenario["factor_weights"][key]
        diff = v3_val - v2_val
        marker = "  ★" if abs(diff) >= 0.05 else ""
        print(f"  {key:<22s} {v2_val:>6.2f} {v3_val:>6.2f} {diff:>+8.2f}{marker}")

    # 追加パラメータ
    if scenario["swing_noise_offset"] != 0:
        print(f"  {'swing_noise_offset':<22s} {'0.00':>6s} {scenario['swing_noise_offset']:>6.2f} {scenario['swing_noise_offset']:>+8.2f}  ★")
    if scenario["independent_loyalty_score"] != 0.3:
        print(f"  {'independent_loyalty':<22s} {'0.30':>6s} {scenario['independent_loyalty_score']:>6.2f} {scenario['independent_loyalty_score'] - 0.3:>+8.2f}  ★")
    if scenario["turnout_boost"] != 0:
        print(f"  {'turnout_boost':<22s} {'0.00':>6s} {scenario['turnout_boost']:>6.2f} {scenario['turnout_boost']:>+8.2f}  ★")


def run_scenario(scenario_key: str, seeds: list[int], personas: int = 100):
    """1つのシナリオを複数シードで実行"""
    scenario = SCENARIOS[scenario_key]

    print(f"\n{'='*70}")
    print(f"シナリオ {scenario_key}: {scenario['name']}")
    print(f"仮説: {scenario['hypothesis']}")
    print(f"{'='*70}")
    print_weight_comparison(scenario)

    experiment_ids = []

    for i, seed in enumerate(seeds):
        print(f"\n{'─'*50}")
        print(f"[{i+1}/{len(seeds)}] {scenario['name']} seed={seed}")
        print(f"{'─'*50}")

        engine = SimulationEngine(
            seed=seed,
            personas_per_district=personas,
            factor_weights=scenario["factor_weights"],
            swing_noise_offset=scenario["swing_noise_offset"],
            independent_loyalty_score=scenario["independent_loyalty_score"],
            turnout_boost=scenario["turnout_boost"],
        )

        experiment_id, results = engine.run_experiment(
            mode="all",
            description=f"{scenario['description']} (seed={seed})",
            tags=scenario["tags"] + [f"seed{seed}"],
        )

        experiment_ids.append(experiment_id)

        # サマリ表示
        summary = engine._build_summary(results)
        print(f"\n  実験ID: {experiment_id}")
        print(f"  投票率: {summary['national_turnout_rate']:.1%}")

        if "total_seats" in summary:
            print(f"\n  合計議席 (SMD + PR):")
            for party, data in sorted(
                summary["total_seats"].items(),
                key=lambda x: -x[1]["total"],
            ):
                if data["total"] > 0:
                    print(f"    {party}: {data['total']}議席 (SMD {data['smd']} + PR {data['pr']})")

            majority = summary.get("majority_threshold", 233)
            ldp_total = summary["total_seats"].get("ldp", {}).get("total", 0)
            print(f"\n  過半数ライン: {majority}議席")
            print(f"  自民党合計: {ldp_total}議席 → {'過半数到達' if ldp_total >= majority else '過半数割れ'}")

    return experiment_ids


def main():
    parser = argparse.ArgumentParser(description="v3 異なる条件での本実験")
    parser.add_argument(
        "--scenario", type=str, choices=["A", "B", "C"], default=None,
        help="実行するシナリオ (未指定で全3シナリオ)"
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int, default=DEFAULT_SEEDS,
        help="シードリスト (default: 42 99 123)"
    )
    parser.add_argument(
        "--personas", type=int, default=100,
        help="選挙区あたりペルソナ数 (default: 100)"
    )
    args = parser.parse_args()

    scenarios_to_run = [args.scenario] if args.scenario else ["A", "B", "C"]

    print("=" * 70)
    print("v3 本実験: 異なる条件での3シナリオ比較")
    print(f"  シナリオ: {scenarios_to_run}")
    print(f"  シード: {args.seeds}")
    print(f"  ペルソナ数/選挙区: {args.personas}")
    print("=" * 70)

    all_experiment_ids = {}

    for scenario_key in scenarios_to_run:
        ids = run_scenario(scenario_key, args.seeds, args.personas)
        all_experiment_ids[scenario_key] = ids

    # 全体サマリ
    print("\n" + "=" * 70)
    print("v3 全実験完了!")
    print("=" * 70)
    for key, ids in all_experiment_ids.items():
        scenario = SCENARIOS[key]
        print(f"\n  シナリオ {key} ({scenario['name']}):")
        for eid in ids:
            print(f"    - {eid}")

    print(f"\n  次のステップ:")
    print(f"    python scripts/aggregate_multi_seed.py --tag v3a_policy_focused")
    print(f"    python scripts/aggregate_multi_seed.py --tag v3b_anti_establishment")
    print(f"    python scripts/aggregate_multi_seed.py --tag v3c_high_turnout")
    print("=" * 70)


if __name__ == "__main__":
    main()
