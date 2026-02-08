"""
全289選挙区フルシミュレーション実行

5つのシードで実行し、統計的ロバストネスを確保する。
結果は results/experiments/ に自動保存される。

使い方:
  python scripts/run_full_simulation.py                  # 5シード全実行
  python scripts/run_full_simulation.py --seeds 42       # 単一シード
  python scripts/run_full_simulation.py --seeds 42 99    # 複数シード指定
"""

import argparse
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.simulation.engine import SimulationEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_SEEDS = [42, 99, 123, 7, 314]


def main():
    parser = argparse.ArgumentParser(description="全289選挙区フルシミュレーション")
    parser.add_argument(
        "--seeds", nargs="+", type=int, default=DEFAULT_SEEDS,
        help="シードリスト (default: 42 99 123 7 314)"
    )
    parser.add_argument(
        "--personas", type=int, default=100,
        help="選挙区あたりペルソナ数 (default: 100)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("第51回衆議院議員総選挙 ペルソナ投票シミュレーション")
    print(f"  モード: 全289選挙区")
    print(f"  シード: {args.seeds}")
    print(f"  ペルソナ数/選挙区: {args.personas}")
    print("=" * 70)

    all_experiment_ids = []

    for i, seed in enumerate(args.seeds):
        print(f"\n{'─' * 50}")
        print(f"[{i+1}/{len(args.seeds)}] シード={seed} で実行中...")
        print(f"{'─' * 50}")

        engine = SimulationEngine(
            seed=seed,
            personas_per_district=args.personas,
        )

        experiment_id, results = engine.run_experiment(
            mode="all",
            description=f"全289選挙区フル実行 (seed={seed})",
            tags=["full", "v1_rule_based", f"seed{seed}"],
        )

        all_experiment_ids.append(experiment_id)

        # 結果サマリ表示
        summary = engine._build_summary(results)
        print(f"\n  実験ID: {experiment_id}")
        print(f"  投票率: {summary['national_turnout_rate']:.1%}")
        print(f"  小選挙区議席:")
        for party, seats in sorted(summary["smd_seats"].items(), key=lambda x: -x[1]):
            print(f"    {party}: {seats}議席")

        if "total_seats" in summary:
            print(f"\n  合計議席 (SMD + PR):")
            for party, data in sorted(
                summary["total_seats"].items(),
                key=lambda x: -x[1]["total"],
            ):
                print(f"    {party}: {data['total']}議席 (SMD {data['smd']} + PR {data['pr']})")

            # 過半数判定
            majority = summary.get("majority_threshold", 233)
            print(f"\n  過半数ライン: {majority}議席")
            ldp_total = summary["total_seats"].get("ldp", {}).get("total", 0)
            print(f"  自民党合計: {ldp_total}議席 → {'過半数到達' if ldp_total >= majority else '過半数割れ'}")

    # 全実験ID一覧
    print("\n" + "=" * 70)
    print("全実験完了!")
    print(f"  実験ID一覧:")
    for eid in all_experiment_ids:
        print(f"    - {eid}")
    print(f"\n  次のステップ:")
    print(f"    python scripts/aggregate_multi_seed.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
