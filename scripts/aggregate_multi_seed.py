"""
マルチシード集計スクリプト

複数シードの全選挙区実行結果を集計し、統計的ロバストネスを分析する。
- 選挙区別の当選者コンセンサス（5/5一致 = 確実、3-4/5 = 接戦）
- 政党別議席の平均・標準偏差・最小・最大
- 投票率の統計

使い方:
  python scripts/aggregate_multi_seed.py
  python scripts/aggregate_multi_seed.py --tag full  # タグでフィルタ
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.experiment_manager import ExperimentManager

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
OUTPUT_DIR = RESULTS_DIR / "aggregated"


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def main():
    parser = argparse.ArgumentParser(description="マルチシード集計")
    parser.add_argument("--tag", default="full", help="フィルタするタグ (default: full)")
    args = parser.parse_args()

    manager = ExperimentManager()
    experiments = manager.list_experiments()

    # タグでフィルタ（fullタグを持つ実験のみ）
    filtered = [e for e in experiments if args.tag in e.get("tags", [])]

    if not filtered:
        print(f"タグ '{args.tag}' の実験が見つかりません")
        print(f"利用可能な実験:")
        for e in experiments:
            print(f"  {e['experiment_id']} tags={e.get('tags', [])}")
        return

    print(f"集計対象: {len(filtered)} 実験")
    for e in filtered:
        print(f"  {e['experiment_id']} (seed={e['parameters'].get('seed', '?')})")

    # 各実験の結果を読み込み
    all_results = []
    for exp_meta in filtered:
        data = manager.load_experiment(exp_meta["experiment_id"])
        all_results.append({
            "experiment_id": exp_meta["experiment_id"],
            "seed": exp_meta["parameters"].get("seed"),
            "districts": data["district_results"],
            "summary": data["summary"],
        })

    # === 選挙区別コンセンサス分析 ===
    district_winners = {}  # district_id -> [winner_party, ...]
    district_turnouts = {}  # district_id -> [turnout_rate, ...]
    district_names = {}

    for run in all_results:
        for d in run["districts"]:
            did = d["district_id"]
            district_names[did] = d.get("district_name", did)
            district_winners.setdefault(did, []).append(d.get("winner_party", ""))
            district_turnouts.setdefault(did, []).append(float(d.get("turnout_rate", 0)))

    # コンセンサス分類
    n_seeds = len(all_results)
    consensus = {"safe": [], "likely": [], "battleground": []}

    for did, winners in sorted(district_winners.items()):
        counter = Counter(winners)
        top_party, top_count = counter.most_common(1)[0]

        entry = {
            "district_id": did,
            "district_name": district_names.get(did, did),
            "consensus_winner": top_party,
            "agreement": f"{top_count}/{n_seeds}",
            "agreement_rate": top_count / n_seeds,
            "winner_counts": dict(counter),
            "turnout_mean": round(mean(district_turnouts.get(did, [])), 4),
            "turnout_std": round(stdev(district_turnouts.get(did, [])), 4),
        }

        if top_count == n_seeds:
            consensus["safe"].append(entry)
        elif top_count >= n_seeds * 0.6:
            consensus["likely"].append(entry)
        else:
            consensus["battleground"].append(entry)

    # === 政党別議席集計 ===
    party_smd_seats = {}  # party -> [seats per seed]
    party_pr_seats = {}
    party_total_seats = {}
    turnout_rates = []

    for run in all_results:
        summary = run["summary"]
        turnout_rates.append(float(summary.get("national_turnout_rate", 0)))

        smd = summary.get("smd_seats", {})
        total_seats = summary.get("total_seats", {})
        pr_seats = summary.get("proportional_seats", {})

        # 全政党のキーを収集
        all_parties = set(smd.keys()) | set(total_seats.keys()) | set(pr_seats.keys())
        for party in all_parties:
            party_smd_seats.setdefault(party, []).append(smd.get(party, 0))
            party_pr_seats.setdefault(party, []).append(pr_seats.get(party, 0))
            if total_seats and party in total_seats:
                t = total_seats[party]
                party_total_seats.setdefault(party, []).append(
                    t["total"] if isinstance(t, dict) else t
                )
            else:
                party_total_seats.setdefault(party, []).append(
                    smd.get(party, 0) + pr_seats.get(party, 0)
                )

    # パディング（シード間で政党が出現しない場合に0を補完）
    for party in party_smd_seats:
        while len(party_smd_seats[party]) < n_seeds:
            party_smd_seats[party].append(0)
        while len(party_pr_seats.get(party, [])) < n_seeds:
            party_pr_seats.setdefault(party, []).append(0)
        while len(party_total_seats.get(party, [])) < n_seeds:
            party_total_seats.setdefault(party, []).append(0)

    party_stats = {}
    for party in sorted(party_total_seats.keys(), key=lambda p: -mean(party_total_seats.get(p, [0]))):
        smd_vals = party_smd_seats.get(party, [0])
        pr_vals = party_pr_seats.get(party, [0])
        total_vals = party_total_seats.get(party, [0])

        party_stats[party] = {
            "smd": {"mean": round(mean(smd_vals), 1), "std": round(stdev(smd_vals), 1), "min": min(smd_vals), "max": max(smd_vals)},
            "pr": {"mean": round(mean(pr_vals), 1), "std": round(stdev(pr_vals), 1), "min": min(pr_vals), "max": max(pr_vals)},
            "total": {"mean": round(mean(total_vals), 1), "std": round(stdev(total_vals), 1), "min": min(total_vals), "max": max(total_vals)},
        }

    # === 出力 ===
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    aggregated = {
        "n_seeds": n_seeds,
        "experiment_ids": [r["experiment_id"] for r in all_results],
        "seeds": [r["seed"] for r in all_results],
        "national": {
            "turnout_mean": round(mean(turnout_rates), 4),
            "turnout_std": round(stdev(turnout_rates), 4),
            "turnout_min": round(min(turnout_rates), 4),
            "turnout_max": round(max(turnout_rates), 4),
        },
        "party_seats": party_stats,
        "consensus": {
            "safe_count": len(consensus["safe"]),
            "likely_count": len(consensus["likely"]),
            "battleground_count": len(consensus["battleground"]),
        },
        "battleground_districts": consensus["battleground"],
        "likely_districts": consensus["likely"],
    }

    output_path = OUTPUT_DIR / "multi_seed_summary.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, ensure_ascii=False, indent=2)

    # === 表示 ===
    print(f"\n{'='*70}")
    print(f"マルチシード集計結果 ({n_seeds}シード)")
    print(f"{'='*70}")

    print(f"\n投票率: {mean(turnout_rates):.1%} (std={stdev(turnout_rates):.1%})")

    print(f"\n政党別議席予測 (SMD + PR = Total):")
    print(f"  {'政党':10s} {'合計':>14s} {'SMD':>14s} {'PR':>14s}")
    print(f"  {'─'*56}")
    for party, stats in party_stats.items():
        t = stats["total"]
        s = stats["smd"]
        p = stats["pr"]
        if t["mean"] < 0.5:
            continue
        print(
            f"  {party:10s} "
            f"{t['mean']:5.1f}±{t['std']:4.1f} ({t['min']:3d}-{t['max']:3d})  "
            f"{s['mean']:5.1f}±{s['std']:4.1f}  "
            f"{p['mean']:5.1f}±{p['std']:4.1f}"
        )

    print(f"\n選挙区コンセンサス:")
    print(f"  確実 (全シード一致):    {len(consensus['safe'])} 選挙区")
    print(f"  優勢 (60%以上一致):     {len(consensus['likely'])} 選挙区")
    print(f"  接戦 (60%未満):         {len(consensus['battleground'])} 選挙区")

    if consensus["battleground"]:
        print(f"\n接戦区一覧:")
        for d in consensus["battleground"]:
            print(f"  {d['district_name']}: {d['winner_counts']} → {d['consensus_winner']}({d['agreement']})")

    print(f"\n結果保存: {output_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
