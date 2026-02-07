"""
バージョン管理付き実験実行CLIスクリプト

使い方:
  # 実験実行
  python scripts/run_experiment.py --mode pilot --seed 42 --description "ベースライン"
  python scripts/run_experiment.py --mode pilot --seed 99 --description "シード変更テスト"
  python scripts/run_experiment.py --mode all --seed 42 --description "本番予測 v1"

  # 実験一覧
  python scripts/run_experiment.py --list

  # 実験詳細
  python scripts/run_experiment.py --show sim_20260208_143022_seed42

  # 実験間比較
  python scripts/run_experiment.py --compare sim_xxx sim_yyy

  # 実選挙結果との比較
  python scripts/run_experiment.py --compare-actual sim_xxx

  # 全実験を実選挙結果と一括比較
  python scripts/run_experiment.py --compare-all-actual
"""

import argparse
import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.services.simulation.engine import SimulationEngine
from app.services.experiment_manager import ExperimentManager
from app.services.experiment_comparison import (
    compare_experiments,
    compare_with_actual,
    format_comparison_report,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def cmd_run(args):
    """実験を実行"""
    logger.info("=" * 60)
    logger.info("実験実行（バージョン管理付き）")
    logger.info("=" * 60)

    engine = SimulationEngine(
        seed=args.seed,
        personas_per_district=args.personas,
    )

    logger.info(f"  モード: {args.mode}")
    logger.info(f"  シード: {args.seed}")
    logger.info(f"  ペルソナ数/選挙区: {args.personas}")
    logger.info(f"  説明: {args.description}")
    if args.tags:
        logger.info(f"  タグ: {args.tags}")
    logger.info("")

    tags = args.tags.split(",") if args.tags else []

    experiment_id, results = engine.run_experiment(
        mode=args.mode,
        description=args.description,
        tags=tags,
    )

    # 結果サマリ表示
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"実験完了: {experiment_id}")
    logger.info("=" * 60)
    logger.info(f"  選挙区数: {len(results)}")

    total_voted = sum(r.turnout_count for r in results)
    total_personas = sum(r.total_personas for r in results)
    logger.info(f"  全国投票率: {total_voted / total_personas:.1%}")

    party_seats = {}
    for r in results:
        if r.winner_party:
            party_seats[r.winner_party] = party_seats.get(r.winner_party, 0) + 1
    logger.info(f"  政党別議席:")
    for party, seats in sorted(party_seats.items(), key=lambda x: -x[1]):
        logger.info(f"    {party}: {seats}")

    exp_dir = BASE_DIR / "results" / "experiments" / experiment_id
    logger.info(f"\n  結果保存先: {exp_dir}")


def cmd_list(args):
    """実験一覧を表示"""
    manager = ExperimentManager()
    experiments = manager.list_experiments()

    if not experiments:
        logger.info("保存済み実験はありません。")
        return

    logger.info(f"保存済み実験: {len(experiments)}件")
    logger.info("=" * 80)
    logger.info(
        f"{'ID':40s} {'日時':20s} {'区数':>4s} {'投票率':>6s} {'説明'}"
    )
    logger.info("-" * 80)

    for exp in experiments:
        exp_id = exp["experiment_id"]
        created = exp.get("created_at", "")[:16]
        districts = exp.get("parameters", {}).get("district_count", "?")
        turnout = exp.get("results_summary", {}).get("national_turnout_rate", 0)
        desc = exp.get("description", "")[:30]
        logger.info(
            f"{exp_id:40s} {created:20s} {districts:>4} {turnout:>5.1%} {desc}"
        )


def cmd_show(args):
    """実験詳細を表示"""
    manager = ExperimentManager()
    try:
        data = manager.load_experiment(args.experiment_id)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    meta = data["metadata"]
    logger.info("=" * 60)
    logger.info(f"実験詳細: {meta['experiment_id']}")
    logger.info("=" * 60)
    logger.info(f"  作成日時: {meta.get('created_at', '')}")
    logger.info(f"  実行時間: {meta.get('duration_seconds', 0):.1f}秒")
    logger.info(f"  説明: {meta.get('description', '')}")
    logger.info(f"  タグ: {meta.get('tags', [])}")

    params = meta.get("parameters", {})
    logger.info(f"\n  パラメータ:")
    logger.info(f"    seed: {params.get('seed')}")
    logger.info(f"    personas_per_district: {params.get('personas_per_district')}")
    logger.info(f"    model: {params.get('model')}")
    logger.info(f"    mode: {params.get('mode')}")
    logger.info(f"    選挙区数: {params.get('district_count')}")

    config = meta.get("config_versions", {})
    weights = config.get("factor_weights", {})
    if weights:
        logger.info(f"\n  投票決定要因の重み:")
        for k, v in weights.items():
            logger.info(f"    {k}: {v}")

    summary = meta.get("results_summary", {})
    logger.info(f"\n  結果サマリ:")
    logger.info(f"    投票率: {summary.get('national_turnout_rate', 0):.1%}")
    logger.info(f"    バリデーション: {'OK' if summary.get('validation_passed') else 'NG'}")
    seats = summary.get("smd_seats", {})
    if seats:
        logger.info(f"    議席数:")
        for party, count in sorted(seats.items(), key=lambda x: -x[1]):
            logger.info(f"      {party}: {count}")

    logger.info(f"\n  環境:")
    env = meta.get("environment", {})
    logger.info(f"    git_commit: {env.get('git_commit', 'unknown')}")

    # 選挙区別結果
    districts = data.get("district_results", [])
    if districts:
        logger.info(f"\n  選挙区別結果 ({len(districts)}件):")
        for r in districts:
            logger.info(
                f"    {r['district_name']}: "
                f"{r['winner']} ({r['winner_party']}) "
                f"vs {r['runner_up']} ({r['runner_up_party']}) "
                f"票差{r['margin']}"
            )


def cmd_compare(args):
    """2つの実験を比較"""
    try:
        report = compare_experiments(args.exp_a, args.exp_b)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(format_comparison_report(report))


def cmd_compare_actual(args):
    """実験と実選挙結果を比較"""
    try:
        report = compare_with_actual(args.experiment_id)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(format_comparison_report(report))


def cmd_compare_all_actual(args):
    """全実験を実選挙結果と一括比較"""
    manager = ExperimentManager()
    experiments = manager.list_experiments()

    if not experiments:
        logger.info("保存済み実験がありません。")
        return

    logger.info("=" * 80)
    logger.info("全実験 vs 実選挙結果 一括比較")
    logger.info("=" * 80)
    logger.info(
        f"{'実験ID':40s} {'一致率':>7s} {'MAE':>5s} {'投票率r':>7s} {'接戦':>6s}"
    )
    logger.info("-" * 80)

    for exp in experiments:
        exp_id = exp["experiment_id"]
        try:
            report = compare_with_actual(exp_id)
            turnout_r = f"{report.turnout_correlation:.3f}" if report.turnout_correlation is not None else "N/A"
            battle = f"{report.battleground_accuracy:.1%}" if report.battleground_accuracy is not None else "N/A"
            logger.info(
                f"{exp_id:40s} {report.winner_match_rate:>6.1%} {report.seat_mae:>5.1f} {turnout_r:>7s} {battle:>6s}"
            )
        except FileNotFoundError:
            logger.info(f"{exp_id:40s} --- 実選挙結果未投入 ---")
            break


def main():
    parser = argparse.ArgumentParser(
        description="実験バージョン管理CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # run コマンド（デフォルト動作もサポート）
    parser.add_argument("--mode", choices=["pilot", "all"], help="実行モード")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード")
    parser.add_argument("--personas", type=int, default=100, help="ペルソナ数/選挙区")
    parser.add_argument("--description", type=str, default="", help="実験の説明")
    parser.add_argument("--tags", type=str, default="", help="タグ（カンマ区切り）")

    # 一覧
    parser.add_argument("--list", action="store_true", help="実験一覧を表示")

    # 詳細
    parser.add_argument("--show", type=str, metavar="EXP_ID", help="実験詳細を表示")

    # 比較
    parser.add_argument("--compare", nargs=2, metavar=("EXP_A", "EXP_B"), help="2実験を比較")

    # 実選挙結果との比較
    parser.add_argument("--compare-actual", type=str, metavar="EXP_ID", help="実選挙結果と比較")

    # 全実験一括比較
    parser.add_argument("--compare-all-actual", action="store_true", help="全実験を実選挙結果と一括比較")

    args = parser.parse_args()

    if args.list:
        cmd_list(args)
    elif args.show:
        args.experiment_id = args.show
        cmd_show(args)
    elif args.compare:
        args.exp_a, args.exp_b = args.compare
        cmd_compare(args)
    elif args.compare_actual:
        args.experiment_id = args.compare_actual
        cmd_compare_actual(args)
    elif args.compare_all_actual:
        cmd_compare_all_actual(args)
    elif args.mode:
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
