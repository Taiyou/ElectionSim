"""
実選挙結果投入スクリプト

2/8の選挙結果をCSVまたはJSONで投入し、保存済み実験との比較を可能にする。

使い方:
  # CSVファイルから投入（シミュレーション出力と同じフォーマット）
  python scripts/load_actual_results.py --csv actual_district_results.csv

  # JSONファイルから投入（全体集計情報を含む）
  python scripts/load_actual_results.py --json actual_results.json

  # 両方を投入
  python scripts/load_actual_results.py --csv actual_district.csv --json actual_summary.json

  # 投票率と議席数だけを手入力（簡易モード）
  python scripts/load_actual_results.py --summary-only \\
      --turnout 0.523 \\
      --seats "ldp:120,chudo:80,ishin:40,jcp:10,dpfp:8,reiwa:5,sansei:3"

CSVフォーマット（district_results.csvと同一）:
  district_id,district_name,winner,winner_party,winner_votes,runner_up,runner_up_party,runner_up_votes,margin,turnout_rate

JSONフォーマット:
  {
    "election_date": "2026-02-08",
    "source": "NHK",
    "national_turnout_rate": 0.523,
    "party_total_seats": {"ldp": {"district": 120, "proportional": 55, "total": 175}, ...}
  }
"""

import argparse
import csv
import json
import logging
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.services.experiment_manager import ACTUAL_DIR

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_csv(csv_path: Path):
    """CSVファイルを actual/ にコピーし検証"""
    if not csv_path.exists():
        logger.error(f"ファイルが見つかりません: {csv_path}")
        sys.exit(1)

    # カラム検証
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"district_id", "winner_party", "turnout_rate"}
        if not required.issubset(set(reader.fieldnames or [])):
            logger.error(f"必須カラムが不足しています: {required - set(reader.fieldnames or [])}")
            sys.exit(1)
        rows = list(reader)

    ACTUAL_DIR.mkdir(parents=True, exist_ok=True)
    dest = ACTUAL_DIR / "district_results.csv"
    shutil.copy2(csv_path, dest)
    logger.info(f"選挙区結果CSV投入完了: {len(rows)}選挙区 -> {dest}")
    return rows


def load_json(json_path: Path):
    """JSONファイルを actual/ にコピー"""
    if not json_path.exists():
        logger.error(f"ファイルが見つかりません: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ACTUAL_DIR.mkdir(parents=True, exist_ok=True)
    dest = ACTUAL_DIR / "actual_results.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"全体集計JSON投入完了 -> {dest}")
    return data


def create_summary_only(turnout: float, seats_str: str):
    """議席数と投票率から簡易JSONを作成"""
    seats = {}
    for pair in seats_str.split(","):
        pair = pair.strip()
        if ":" in pair:
            party, count = pair.split(":", 1)
            seats[party.strip()] = int(count.strip())

    data = {
        "election_date": "2026-02-08",
        "source": "手入力",
        "national_turnout_rate": turnout,
        "party_total_seats": {
            party: {"total": count}
            for party, count in seats.items()
        },
    }

    ACTUAL_DIR.mkdir(parents=True, exist_ok=True)
    dest = ACTUAL_DIR / "actual_results.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"簡易集計JSON作成完了 -> {dest}")
    logger.info(f"  投票率: {turnout:.1%}")
    logger.info(f"  議席数:")
    for party, count in sorted(seats.items(), key=lambda x: -x[1]):
        logger.info(f"    {party}: {count}")

    return data


def main():
    parser = argparse.ArgumentParser(
        description="実選挙結果投入ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--csv", type=str, help="選挙区結果CSVファイルパス")
    parser.add_argument("--json", type=str, help="全体集計JSONファイルパス")
    parser.add_argument("--summary-only", action="store_true", help="簡易モード（議席数・投票率のみ）")
    parser.add_argument("--turnout", type=float, help="全国投票率（簡易モード用）")
    parser.add_argument("--seats", type=str, help="政党別議席数（簡易モード用: 'ldp:120,chudo:80,...'）")

    args = parser.parse_args()

    if args.summary_only:
        if not args.turnout or not args.seats:
            logger.error("簡易モードでは --turnout と --seats が必要です")
            sys.exit(1)
        create_summary_only(args.turnout, args.seats)
    elif args.csv or args.json:
        if args.csv:
            load_csv(Path(args.csv))
        if args.json:
            load_json(Path(args.json))
    else:
        parser.print_help()
        sys.exit(1)

    logger.info(f"\n投入先ディレクトリ: {ACTUAL_DIR}")
    logger.info("比較コマンド: python scripts/run_experiment.py --compare-actual <EXPERIMENT_ID>")


if __name__ == "__main__":
    main()
