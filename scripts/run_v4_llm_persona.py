"""
v4 LLMペルソナ投票実験

全ペルソナの投票行動をLLM（Claude Sonnet via OpenRouter）に判断させる。
ルールベース（v2）との比較が目的。

使い方:
  # v4a: パイロット10区
  python scripts/run_v4_llm_persona.py --mode pilot --seed 42

  # v4b: 全289区（3シード）
  python scripts/run_v4_llm_persona.py --mode all --seed 42
  python scripts/run_v4_llm_persona.py --mode all --seed 99
  python scripts/run_v4_llm_persona.py --mode all --seed 123
"""

import asyncio
import argparse
import csv
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path

# プロジェクトルートをパスに追加
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.services.simulation.persona_generator import (
    generate_personas_for_district,
    load_archetype_config,
    load_candidates,
    load_district_data,
)
from backend.app.services.simulation.llm_voter import run_llm_batch, DEFAULT_MODEL
from backend.app.services.simulation.result_aggregator import aggregate_district_results
from backend.app.services.simulation.validators import validate_results
from backend.app.services.simulation.engine import dhondt_allocation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = BASE_DIR / "backend" / "app" / "data"
RESULTS_DIR = BASE_DIR / "results" / "experiments"
EXPERIMENTS_DIR = BASE_DIR / "experiments"

PILOT_DISTRICTS = [
    "13_1", "01_11", "27_1", "47_1", "23_1",
    "05_1", "14_1", "26_1", "40_1", "32_1",
]


async def run_district_llm(
    district_row: dict,
    archetypes: list[dict],
    candidates_by_district: dict,
    seed: int,
    personas_per_district: int,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
):
    """1選挙区のLLMペルソナシミュレーション"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
    district_name = district_row.get("選挙区", district_id)

    logger.info(f"選挙区開始: {district_name} ({district_id})")

    # ペルソナ生成（ルールベースと同一）
    personas = generate_personas_for_district(
        district_row, archetypes, personas_per_district, seed
    )

    # 候補者データ
    candidates = candidates_by_district.get(district_id, [])
    if not candidates:
        alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
        candidates = candidates_by_district.get(alt_id, [])

    if not candidates:
        logger.warning(f"  候補者データなし: {district_id}")
        return None

    # LLM投票
    decisions = await run_llm_batch(
        district_name=district_name,
        area_description=district_row.get("対象地域", ""),
        candidates=candidates,
        district_context=district_row,
        personas=personas,
        batch_size=batch_size,
        model=model,
        temperature=temperature,
        concurrency=concurrency,
    )

    # 集計
    result = aggregate_district_results(
        district_id=district_id,
        district_name=district_name,
        personas=personas,
        decisions=decisions,
        candidates=candidates,
    )

    voted = sum(1 for d in decisions if d.will_vote)
    logger.info(
        f"  完了: {district_name} 投票{voted}/{len(personas)}名 "
        f"当選: {result.winner} ({result.winner_party})"
    )

    return result, decisions


async def run_experiment(args):
    """実験全体を実行"""

    logger.info("=" * 70)
    tag = "v4a_llm_pilot" if args.mode == "pilot" else "v4b_llm_full"
    logger.info(f"v4 LLMペルソナ投票実験: {tag}")
    logger.info(f"  モード: {args.mode}")
    logger.info(f"  シード: {args.seed}")
    logger.info(f"  モデル: {args.model}")
    logger.info(f"  温度: {args.temperature}")
    logger.info(f"  バッチサイズ: {args.batch_size}")
    logger.info(f"  同時実行数: {args.concurrency}")
    logger.info("=" * 70)

    # データ読み込み
    config = load_archetype_config()
    archetypes = config["persona_archetypes"]
    districts = load_district_data()
    candidates_by_district = load_candidates()

    # 対象選挙区
    if args.mode == "pilot":
        target_ids = set(PILOT_DISTRICTS)
        target_districts = [d for d in districts
                           if f"{d['都道府県コード'].zfill(2)}_{d['区番号']}" in target_ids]
    else:
        target_districts = districts

    logger.info(f"  対象選挙区: {len(target_districts)}区")

    start_time = time.time()
    results = []
    all_decisions_by_district = {}

    for i, district_row in enumerate(target_districts):
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        result_tuple = await run_district_llm(
            district_row=district_row,
            archetypes=archetypes,
            candidates_by_district=candidates_by_district,
            seed=args.seed,
            personas_per_district=args.personas,
            model=args.model,
            temperature=args.temperature,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
        )

        if result_tuple is not None:
            result, decisions = result_tuple
            results.append(result)
            all_decisions_by_district[district_id] = decisions

        if (i + 1) % 10 == 0:
            logger.info(f"進捗: {i + 1}/{len(target_districts)} 選挙区完了")

    duration = time.time() - start_time
    logger.info(f"\n全選挙区完了: {len(results)}区, {duration:.1f}秒")

    # 結果保存
    experiment_id = _save_results(
        results=results,
        all_decisions=all_decisions_by_district,
        args=args,
        tag=tag,
        duration=duration,
    )

    # サマリ表示
    _print_summary(results, experiment_id)

    return experiment_id


def _save_results(results, all_decisions, args, tag, duration):
    """結果をファイルに保存"""
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    experiment_id = f"v4_{now.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}"

    # results/experiments/ に保存
    exp_dir = RESULTS_DIR / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # 選挙区結果CSV
    csv_path = exp_dir / "district_results.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "district_id", "district_name", "total_personas", "turnout_count",
            "turnout_rate", "winner", "winner_party", "winner_votes",
            "runner_up", "runner_up_party", "runner_up_votes", "margin",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "district_id": r.district_id,
                "district_name": r.district_name,
                "total_personas": r.total_personas,
                "turnout_count": r.turnout_count,
                "turnout_rate": r.turnout_rate,
                "winner": r.winner,
                "winner_party": r.winner_party,
                "winner_votes": r.winner_votes,
                "runner_up": r.runner_up,
                "runner_up_party": r.runner_up_party,
                "runner_up_votes": r.runner_up_votes,
                "margin": r.margin,
            })

    # 比例代表結果
    _save_proportional(results, exp_dir)

    # LLM投票理由を含む詳細JSON
    decisions_data = {}
    for district_id, decisions in all_decisions.items():
        decisions_data[district_id] = []
        for d in decisions:
            entry = {
                "persona_id": d.persona_id,
                "will_vote": d.will_vote,
                "abstention_reason": d.abstention_reason,
                "smd_candidate": d.smd_candidate,
                "smd_party": d.smd_party,
                "proportional_party": d.proportional_party,
                "confidence": d.confidence,
                "swing_level": d.swing_level,
            }
            if d.score_breakdown and d.score_breakdown.get("method") == "llm":
                entry["smd_reason"] = d.score_breakdown.get("smd_reason", "")
                entry["proportional_reason"] = d.score_breakdown.get("proportional_reason", "")
                entry["swing_factors"] = d.score_breakdown.get("swing_factors", [])
            decisions_data[district_id].append(entry)

    decisions_path = exp_dir / "persona_decisions.json"
    with open(decisions_path, "w", encoding="utf-8") as f:
        json.dump(decisions_data, f, ensure_ascii=False, indent=2)

    # サマリJSON
    summary = _build_summary(results)
    summary_path = exp_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # バリデーション
    report = validate_results(results)
    validation_path = exp_dir / "validation_report.json"
    with open(validation_path, "w", encoding="utf-8") as f:
        json.dump({
            "passed": report.passed,
            "checks": report.checks,
            "warnings": report.warnings,
            "errors": report.errors,
        }, f, ensure_ascii=False, indent=2)

    # メタデータ
    metadata = {
        "experiment_id": experiment_id,
        "created_at": now.isoformat(),
        "status": "completed",
        "duration_seconds": round(duration, 2),
        "description": f"v4 LLMペルソナ投票 ({args.mode}, seed={args.seed})",
        "tags": [tag, f"seed{args.seed}", "llm_persona"],
        "parameters": {
            "seed": args.seed,
            "personas_per_district": args.personas,
            "model": args.model,
            "temperature": args.temperature,
            "batch_size": args.batch_size,
            "concurrency": args.concurrency,
            "mode": args.mode,
            "district_count": len(results),
            "total_personas": sum(r.total_personas for r in results),
            "method": "llm_all_personas",
        },
        "results_summary": {
            "national_turnout_rate": summary["national_turnout_rate"],
            "smd_seats": summary["smd_seats"],
            "validation_passed": report.passed,
        },
    }
    metadata_path = exp_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # experiments/ にも experiment.json を保存
    exp_log_dir = EXPERIMENTS_DIR / tag
    exp_log_dir.mkdir(parents=True, exist_ok=True)
    exp_json_path = exp_log_dir / "experiment.json"
    with open(exp_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"結果保存: {exp_dir}")
    return experiment_id


def _save_proportional(results, exp_dir):
    """比例代表結果CSV"""
    blocks_path = DATA_DIR / "proportional_blocks.json"
    prefs_path = DATA_DIR / "prefectures.json"

    try:
        with open(blocks_path, "r", encoding="utf-8") as f:
            blocks = json.load(f)
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefectures = json.load(f)
    except FileNotFoundError:
        return

    pref_to_block = {p["code"]: p.get("proportional_block", "") for p in prefectures}
    block_votes = {}

    for r in results:
        pref_code = int(r.district_id.split("_")[0])
        block_name = pref_to_block.get(pref_code, "unknown")
        if block_name not in block_votes:
            block_votes[block_name] = {}
        for party, votes in r.proportional_votes.items():
            block_votes[block_name][party] = block_votes[block_name].get(party, 0) + votes

    block_seats_map = {b["id"]: b.get("total_seats", b.get("seats", 0)) for b in blocks}

    csv_path = exp_dir / "proportional_results.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["block", "party", "vote_count", "vote_share", "seats_won"])
        writer.writeheader()
        for block_id, votes in block_votes.items():
            total = sum(votes.values())
            seats = block_seats_map.get(block_id, 0)
            allocated = dhondt_allocation(votes, seats) if seats > 0 else {}
            for party, count in sorted(votes.items(), key=lambda x: -x[1]):
                writer.writerow({
                    "block": block_id,
                    "party": party,
                    "vote_count": count,
                    "vote_share": round(count / total, 4) if total > 0 else 0,
                    "seats_won": allocated.get(party, 0),
                })


def _build_summary(results):
    """全体サマリ構築"""
    party_seats = {}
    total_turnout = 0
    total_personas = 0

    for r in results:
        total_turnout += r.turnout_count
        total_personas += r.total_personas
        if r.winner_party:
            party_seats[r.winner_party] = party_seats.get(r.winner_party, 0) + 1

    return {
        "total_districts": len(results),
        "total_personas": total_personas,
        "national_turnout_rate": round(total_turnout / total_personas, 4) if total_personas else 0,
        "smd_seats": party_seats,
        "method": "llm_all_personas",
    }


def _print_summary(results, experiment_id):
    """サマリ表示"""
    summary = _build_summary(results)

    print(f"\n{'=' * 60}")
    print(f"実験完了: {experiment_id}")
    print(f"{'=' * 60}")
    print(f"  選挙区数: {summary['total_districts']}")
    print(f"  投票率: {summary['national_turnout_rate']:.1%}")
    print(f"  政党別議席 (SMD):")
    for party, seats in sorted(summary["smd_seats"].items(), key=lambda x: -x[1]):
        print(f"    {party}: {seats}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="v4 LLMペルソナ投票実験")
    parser.add_argument("--mode", choices=["pilot", "all"], default="pilot")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--personas", type=int, default=100)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--batch-size", type=int, default=15)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
