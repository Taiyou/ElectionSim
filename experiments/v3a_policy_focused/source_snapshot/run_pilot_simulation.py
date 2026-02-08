"""
パイロットシミュレーション実行スクリプト

10選挙区でシミュレーションを実行し、結果をバリデーションする。
LLM呼び出しなし（ルールベースのみ）で動作確認を行う。
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.services.simulation.engine import SimulationEngine
from app.services.simulation.validators import validate_results

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("ペルソナ投票シミュレーション パイロット実行")
    logger.info("=" * 60)

    # エンジン初期化
    engine = SimulationEngine(seed=42, personas_per_district=100)

    logger.info(f"\nデータ読み込み完了:")
    logger.info(f"  選挙区数: {len(engine.districts)}")
    logger.info(f"  候補者データ: {sum(len(v) for v in engine.candidates_by_district.values())} 名")
    logger.info(f"  アーキタイプ数: {len(engine.archetypes)}")

    # パイロット実行
    logger.info(f"\nパイロット実行開始...")
    results = engine.run_pilot()

    logger.info(f"\n{'=' * 60}")
    logger.info(f"パイロット結果 ({len(results)} 選挙区)")
    logger.info(f"{'=' * 60}")

    for r in results:
        logger.info(f"\n--- {r.district_name} ({r.district_id}) ---")
        logger.info(f"  投票率: {r.turnout_rate:.1%} ({r.turnout_count}/{r.total_personas})")
        logger.info(f"  当選: {r.winner} ({r.winner_party}) {r.winner_votes}票")
        logger.info(f"  次点: {r.runner_up} ({r.runner_up_party}) {r.runner_up_votes}票")
        logger.info(f"  票差: {r.margin}")

        # 全候補者の得票
        if r.smd_votes:
            logger.info(f"  小選挙区得票:")
            for name, votes in sorted(r.smd_votes.items(), key=lambda x: -x[1]):
                logger.info(f"    {name}: {votes}票")

        # 比例得票
        if r.proportional_votes:
            logger.info(f"  比例得票:")
            for party, votes in sorted(r.proportional_votes.items(), key=lambda x: -x[1]):
                logger.info(f"    {party}: {votes}票")

        # アーキタイプ別投票率
        if r.archetype_breakdown:
            logger.info(f"  アーキタイプ別:")
            for arch, data in sorted(r.archetype_breakdown.items()):
                rate = data['voted'] / data['count'] if data['count'] > 0 else 0
                logger.info(f"    {arch}: {data['count']}名, 投票率{rate:.0%}")

    # バリデーション
    logger.info(f"\n{'=' * 60}")
    logger.info(f"バリデーション")
    logger.info(f"{'=' * 60}")

    report = validate_results(results)
    logger.info(report.summary())

    # 結果出力
    output_dir = BASE_DIR / "results" / "pilot"
    engine.export_results(results, output_dir)
    logger.info(f"\n結果出力先: {output_dir}")

    return results


if __name__ == "__main__":
    main()
