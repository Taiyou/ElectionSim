"""
v9a ハイブリッドアンサンブル実験（ルールベース + LLM）

v2の多シード結果で「安定区」と「接戦区」を分類し、
接戦区のみLLMで精密シミュレーションすることで、コスト効率を最適化する。

アーキテクチャ:
  Step 1: v2の多シード結果から安定区/接戦区を分類
    → 安定区（全シード一致）: ルールベース結果をそのまま採用
    → 接戦区（一致率<100%）: v8aアーキテクチャでLLM実行

  Step 2: 接戦区のみLLM実行（v8aデカップリング方式）
  Step 3: アンサンブル統合

使い方:
  # パイロット（接戦区のみ）
  python scripts/run_v9_hybrid_ensemble.py --seed 42

  # カスタム閾値（agreement_rate < 0.8 のみLLM実行）
  python scripts/run_v9_hybrid_ensemble.py --seed 42 --threshold 0.8
"""

from __future__ import annotations

import asyncio
import argparse
import csv
import json
import logging
import random
import sys
import time
from dataclasses import asdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.services.simulation.persona_generator import (
    generate_personas_for_district,
    load_archetype_config,
    load_candidates,
    load_district_data,
)
from backend.app.services.simulation.llm_voter import (
    call_openrouter_async,
    parse_llm_response,
    DEFAULT_MODEL,
)
from backend.app.services.simulation.prompts import (
    CALIBRATED_SYSTEM_PROMPT,
    build_calibrated_batch_prompt,
)
from backend.app.services.simulation.result_aggregator import (
    aggregate_district_results,
    calibrate_decisions,
)
from backend.app.services.simulation.vote_calculator import (
    VoteDecision,
    determine_turnout,
    calculate_vote,
)
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
AGGREGATED_DIR = BASE_DIR / "results" / "aggregated"

# 天候補正マップ（run_v8と同一）
WEATHER_MODIFIERS = {
    "01": -0.10, "02": -0.08, "03": -0.05, "05": -0.08,
    "06": -0.07, "07": -0.04, "15": -0.07, "16": -0.05,
    "17": -0.05, "18": -0.05, "19": -0.03, "20": -0.04,
    "04": -0.03, "08": -0.02, "09": -0.02, "10": -0.02,
}


def get_weather_modifier(district_id: str) -> float:
    pref_code = district_id.split("_")[0]
    return WEATHER_MODIFIERS.get(pref_code, -0.02)


def load_consensus_data() -> dict:
    """v2多シード結果から選挙区の安定度データを読み込む"""
    summary_path = AGGREGATED_DIR / "multi_seed_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def classify_districts(consensus_data: dict, threshold: float) -> tuple[set, set, dict]:
    """選挙区を安定区と接戦区に分類する

    Args:
        consensus_data: multi_seed_summary.json の内容
        threshold: LLM実行の閾値（agreement_rate がこの値未満の選挙区でLLM実行）

    Returns:
        (safe_district_ids, contested_district_ids, consensus_winners)
    """
    contested = set()
    consensus_winners = {}

    # battleground_districts（最も不安定）
    for d in consensus_data.get("battleground_districts", []):
        district_id = d["district_id"]
        contested.add(district_id)
        consensus_winners[district_id] = {
            "winner": d["consensus_winner"],
            "agreement_rate": d["agreement_rate"],
            "winner_counts": d["winner_counts"],
        }

    # likely_districts（やや不安定）
    for d in consensus_data.get("likely_districts", []):
        district_id = d["district_id"]
        if d["agreement_rate"] < threshold:
            contested.add(district_id)
        consensus_winners[district_id] = {
            "winner": d["consensus_winner"],
            "agreement_rate": d["agreement_rate"],
            "winner_counts": d["winner_counts"],
        }

    # safe_districts は consensus_data に含まれない（全シード一致）
    all_contested = contested
    return set(), all_contested, consensus_winners


async def run_district_llm_calibrated(
    district_row: dict,
    archetypes: list[dict],
    candidates_by_district: dict,
    seed: int,
    personas_per_district: int,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
    calibration_strength: float,
):
    """接戦区のLLMシミュレーション（v8aと同一ロジック）"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
    district_name = district_row.get("選挙区", district_id)

    random.seed(seed)
    personas = generate_personas_for_district(
        district_row, archetypes, personas_per_district, seed
    )

    candidates = candidates_by_district.get(district_id, [])
    if not candidates:
        alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
        candidates = candidates_by_district.get(alt_id, [])

    if not candidates:
        return None

    # Stage 1: ルールベース投票率判定
    random.seed(seed + hash(district_id))
    weather_mod = get_weather_modifier(district_id)

    voting_personas = []
    abstaining_decisions = []

    for persona in personas:
        will_vote, reason = determine_turnout(persona, weather_modifier=weather_mod)
        if will_vote:
            voting_personas.append(persona)
        else:
            abstaining_decisions.append(VoteDecision(
                persona_id=persona.persona_id,
                will_vote=False,
                abstention_reason=reason,
                swing_level=persona.swing_tendency,
            ))

    if not voting_personas:
        return None

    # Stage 2: LLM投票先決定
    all_llm_decisions = [None] * len(voting_personas)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_batch(batch_start, batch_personas):
        async with semaphore:
            persona_dicts = [asdict(p) for p in batch_personas]
            prompt = build_calibrated_batch_prompt(
                district_name=district_name,
                area_description=district_row.get("対象地域", ""),
                candidates=candidates,
                district_context=district_row,
                personas=persona_dicts,
            )

            for attempt in range(3):
                try:
                    response = await call_openrouter_async(
                        model=model,
                        system_prompt=CALIBRATED_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        temperature=temperature,
                    )
                    decisions = parse_llm_response(response, batch_personas, candidates)

                    for j, decision in enumerate(decisions):
                        global_idx = batch_start + j
                        if global_idx < len(all_llm_decisions):
                            decision.will_vote = True
                            all_llm_decisions[global_idx] = decision
                    break
                except Exception as e:
                    logger.warning(f"  バッチ {batch_start} リトライ {attempt + 1}: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)

            await asyncio.sleep(1.0)

    tasks = []
    for i in range(0, len(voting_personas), batch_size):
        batch = voting_personas[i:i + batch_size]
        tasks.append(process_batch(i, batch))

    await asyncio.gather(*tasks)

    llm_decisions = []
    for i, decision in enumerate(all_llm_decisions):
        if decision is None:
            fallback_candidate = candidates[0]
            for c in candidates:
                if c.get("status") == "incumbent":
                    fallback_candidate = c
                    break
            llm_decisions.append(VoteDecision(
                persona_id=voting_personas[i].persona_id,
                will_vote=True,
                smd_candidate=fallback_candidate["candidate_name"],
                smd_party=fallback_candidate.get("party_id", ""),
                proportional_party=fallback_candidate.get("party_id", ""),
                confidence=0.3,
                swing_level=voting_personas[i].swing_tendency,
            ))
        else:
            llm_decisions.append(decision)

    # Stage 3: キャリブレーション
    calibrated = calibrate_decisions(
        llm_decisions, district_context=district_row,
        strength=calibration_strength, seed=seed,
    )

    all_decisions = abstaining_decisions + calibrated

    result = aggregate_district_results(
        district_id=district_id,
        district_name=district_name,
        personas=personas,
        decisions=all_decisions,
        candidates=candidates,
    )

    return result, all_decisions


def run_district_rule_based(
    district_row: dict,
    archetypes: list[dict],
    candidates_by_district: dict,
    seed: int,
    personas_per_district: int,
):
    """安定区のルールベースシミュレーション"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
    district_name = district_row.get("選挙区", district_id)

    random.seed(seed)
    personas = generate_personas_for_district(
        district_row, archetypes, personas_per_district, seed
    )

    candidates = candidates_by_district.get(district_id, [])
    if not candidates:
        alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
        candidates = candidates_by_district.get(alt_id, [])

    if not candidates:
        return None

    random.seed(seed + hash(district_id))
    decisions = []
    for persona in personas:
        decision = calculate_vote(persona, candidates, district_row)
        decisions.append(decision)

    result = aggregate_district_results(
        district_id=district_id,
        district_name=district_name,
        personas=personas,
        decisions=decisions,
        candidates=candidates,
    )

    return result, decisions


async def run_experiment(args):
    """v9a ハイブリッドアンサンブル実験実行"""

    tag = "v9a_hybrid_ensemble"

    logger.info("=" * 70)
    logger.info(f"v9a ハイブリッドアンサンブル実験")
    logger.info(f"  シード: {args.seed}")
    logger.info(f"  接戦区閾値: agreement_rate < {args.threshold}")
    logger.info(f"  キャリブレーション強度: {args.calibration_strength}")
    logger.info("=" * 70)

    # データ読み込み
    config = load_archetype_config()
    archetypes = config["persona_archetypes"]
    districts = load_district_data()
    candidates_by_district = load_candidates()

    # 選挙区分類
    consensus_data = load_consensus_data()
    _, contested_ids, consensus_info = classify_districts(consensus_data, args.threshold)

    logger.info(f"  接戦区: {len(contested_ids)}区（LLM実行）")
    logger.info(f"  安定区: {289 - len(contested_ids)}区（ルールベース）")

    start_time = time.time()
    results = []
    all_decisions_by_district = {}
    method_by_district = {}

    # 安定区: ルールベース
    safe_count = 0
    for district_row in districts:
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        if district_id in contested_ids:
            continue

        result_tuple = run_district_rule_based(
            district_row=district_row,
            archetypes=archetypes,
            candidates_by_district=candidates_by_district,
            seed=args.seed,
            personas_per_district=args.personas,
        )

        if result_tuple:
            result, decisions = result_tuple
            results.append(result)
            all_decisions_by_district[district_id] = decisions
            method_by_district[district_id] = "rule_based"
            safe_count += 1

    logger.info(f"安定区完了: {safe_count}区")

    # 接戦区: LLM
    llm_count = 0
    for district_row in districts:
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        if district_id not in contested_ids:
            continue

        logger.info(f"LLM接戦区: {district_row.get('選挙区', district_id)} "
                     f"(consensus: {consensus_info.get(district_id, {}).get('agreement_rate', '?')})")

        result_tuple = await run_district_llm_calibrated(
            district_row=district_row,
            archetypes=archetypes,
            candidates_by_district=candidates_by_district,
            seed=args.seed,
            personas_per_district=args.personas,
            model=args.model,
            temperature=args.temperature,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
            calibration_strength=args.calibration_strength,
        )

        if result_tuple:
            result, decisions = result_tuple
            results.append(result)
            all_decisions_by_district[district_id] = decisions
            method_by_district[district_id] = "llm_calibrated"
            llm_count += 1

    duration = time.time() - start_time
    logger.info(f"\n全選挙区完了: {len(results)}区 ({safe_count} rule + {llm_count} LLM), {duration:.1f}秒")

    # 結果保存
    experiment_id = _save_results(
        results=results,
        all_decisions=all_decisions_by_district,
        method_by_district=method_by_district,
        consensus_info=consensus_info,
        args=args,
        tag=tag,
        duration=duration,
        safe_count=safe_count,
        llm_count=llm_count,
    )

    _print_summary(results, experiment_id, safe_count, llm_count)
    return experiment_id


def _save_results(results, all_decisions, method_by_district, consensus_info,
                  args, tag, duration, safe_count, llm_count):
    """結果保存"""
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    experiment_id = f"v9a_{now.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}"

    exp_dir = RESULTS_DIR / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # 選挙区結果CSV
    csv_path = exp_dir / "district_results.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "district_id", "district_name", "total_personas", "turnout_count",
            "turnout_rate", "winner", "winner_party", "winner_votes",
            "runner_up", "runner_up_party", "runner_up_votes", "margin", "method",
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
                "method": method_by_district.get(r.district_id, "unknown"),
            })

    # 比例代表結果
    _save_proportional(results, exp_dir)

    # サマリ
    party_seats = {}
    total_turnout = sum(r.turnout_count for r in results)
    total_personas = sum(r.total_personas for r in results)
    for r in results:
        if r.winner_party:
            party_seats[r.winner_party] = party_seats.get(r.winner_party, 0) + 1

    summary = {
        "total_districts": len(results),
        "total_personas": total_personas,
        "national_turnout_rate": round(total_turnout / total_personas, 4) if total_personas else 0,
        "smd_seats": party_seats,
        "method": "hybrid_ensemble",
        "rule_based_districts": safe_count,
        "llm_districts": llm_count,
    }
    with open(exp_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # メタデータ
    metadata = {
        "experiment_id": experiment_id,
        "created_at": now.isoformat(),
        "status": "completed",
        "duration_seconds": round(duration, 2),
        "description": f"v9a ハイブリッドアンサンブル (seed={args.seed})",
        "tags": [tag, f"seed{args.seed}", "hybrid", "ensemble"],
        "parameters": {
            "seed": args.seed,
            "personas_per_district": args.personas,
            "model": args.model,
            "temperature": args.temperature,
            "batch_size": args.batch_size,
            "concurrency": args.concurrency,
            "threshold": args.threshold,
            "calibration_strength": args.calibration_strength,
            "method": "hybrid_ensemble",
            "rule_based_districts": safe_count,
            "llm_districts": llm_count,
        },
        "methodology": {
            "classification": f"v2多シード合意率 < {args.threshold} の選挙区でLLM実行",
            "safe_districts": "ルールベース（v2と同一モデル）",
            "contested_districts": "v8aデカップリング方式（Stage 1 ルール投票率 + Stage 2 LLM投票先 + Stage 3 キャリブレーション）",
        },
        "results_summary": {
            "national_turnout_rate": summary["national_turnout_rate"],
            "smd_seats": party_seats,
        },
    }
    with open(exp_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    exp_log_dir = EXPERIMENTS_DIR / tag
    exp_log_dir.mkdir(parents=True, exist_ok=True)
    with open(exp_log_dir / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"結果保存: {exp_dir}")
    return experiment_id


def _save_proportional(results, exp_dir):
    """比例代表結果"""
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


def _print_summary(results, experiment_id, safe_count, llm_count):
    """サマリ表示"""
    party_seats = {}
    total_turnout = sum(r.turnout_count for r in results)
    total_personas = sum(r.total_personas for r in results)
    for r in results:
        if r.winner_party:
            party_seats[r.winner_party] = party_seats.get(r.winner_party, 0) + 1

    turnout_rate = total_turnout / total_personas if total_personas else 0

    print(f"\n{'=' * 60}")
    print(f"実験完了: {experiment_id}")
    print(f"{'=' * 60}")
    print(f"  選挙区数: {len(results)} ({safe_count} rule + {llm_count} LLM)")
    print(f"  投票率: {turnout_rate:.1%}")
    print(f"  政党別議席 (SMD):")
    for party, seats in sorted(party_seats.items(), key=lambda x: -x[1]):
        print(f"    {party}: {seats}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="v9a ハイブリッドアンサンブル実験")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--personas", type=int, default=100)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--batch-size", type=int, default=15)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--threshold", type=float, default=1.0,
        help="LLM実行の閾値: agreement_rate < threshold の選挙区でLLM実行 (default=1.0: 全接戦区)",
    )
    parser.add_argument(
        "--calibration-strength", type=float, default=0.3,
        help="キャリブレーション強度 (default=0.3)",
    )
    args = parser.parse_args()

    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
