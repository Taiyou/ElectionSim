"""
v10a 人口統計ペルソナ + LLM投票実験（記憶なし / ベースライン）

v8aと同じ3ステージパイプラインを使用するが、ペルソナ生成を
15アーキタイプベースから人口統計データベースに切り替える。

  Stage 1: ルールベース投票率判定（人口統計属性から算出）
  Stage 2: LLM投票先決定（全投票者をバッチ処理）
  Stage 3: 事後キャリブレーション

使い方:
  python scripts/run_v10a_demographic.py --mode pilot --seed 42
  python scripts/run_v10a_demographic.py --mode all --seed 42
  python scripts/run_v10a_demographic.py --mode pilot --seed 42 --no-calibration
"""

from __future__ import annotations

import asyncio
import argparse
import csv
import json
import logging
import os
import random
import sys
import time
from dataclasses import asdict
from pathlib import Path

# プロジェクトルートをパスに追加
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.services.simulation.demographic_persona_generator import (
    DemographicPersona,
    generate_demographic_personas_for_district,
    load_district_data,
    load_candidates,
)
from backend.app.services.simulation.llm_voter import (
    call_openrouter_async,
    parse_llm_response,
    DEFAULT_MODEL,
)
from backend.app.services.simulation.prompts import (
    CALIBRATED_SYSTEM_PROMPT,
    build_calibrated_batch_prompt,
    DEFAULT_POLITICAL_CLIMATE,
)
from backend.app.services.simulation.result_aggregator import (
    aggregate_district_results,
    calibrate_decisions,
    compute_calibration_signals,
)
from backend.app.services.simulation.vote_calculator import VoteDecision
from backend.app.services.simulation.validators import validate_results
from backend.app.services.simulation.engine import dhondt_allocation
from backend.app.services.simulation.weather_service import WeatherService

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

# 天候補正: WeatherServiceから取得（静的フォールバック用の旧マップも保持）
_STATIC_WEATHER_MODIFIERS = {
    "01": -0.10, "02": -0.08, "03": -0.05, "05": -0.08,
    "06": -0.07, "07": -0.04, "15": -0.07, "16": -0.05,
    "17": -0.05, "18": -0.05, "19": -0.03, "20": -0.04,
    "04": -0.03, "08": -0.02, "09": -0.02, "10": -0.02,
}

# グローバル天気キャッシュ（run_experiment内で初期化）
_weather_cache: dict = {}


def get_weather_modifier(district_id: str) -> float:
    pref_code = district_id.split("_")[0]
    if _weather_cache and pref_code in _weather_cache:
        return _weather_cache[pref_code].turnout_modifier
    return _STATIC_WEATHER_MODIFIERS.get(pref_code, -0.02)


def get_weather_description(district_id: str) -> str:
    pref_code = district_id.split("_")[0]
    if _weather_cache and pref_code in _weather_cache:
        return _weather_cache[pref_code].weather_description_ja
    return "大雪・強烈寒波"


def determine_turnout_demographic(
    persona: DemographicPersona,
    weather_modifier: float = 0.0,
    rng: random.Random | None = None,
) -> tuple[bool, str | None]:
    """人口統計ペルソナの投票/棄権をルールベースで判定（v10a Stage 1）

    persona.turnout_probability には既に天候補正が含まれているが、
    v8a方式との互換性のため追加の weather_modifier も適用可能。
    """
    if rng is None:
        rng = random.Random()
    adjusted_prob = max(0.05, min(0.95, persona.turnout_probability + weather_modifier))
    will_vote = rng.random() < adjusted_prob

    if not will_vote:
        reasons = []
        if persona.age <= 29:
            reasons.append("若年層の投票意欲低下")
        if persona.political_engagement == "low":
            reasons.append("政治関心が低い")
        if persona.income_bracket == "低":
            reasons.append("生活困窮で投票所に行く余裕がない")
        if weather_modifier < -0.05:
            reasons.append("大雪による外出困難")
        elif weather_modifier < 0:
            reasons.append("悪天候")
        reason = "、".join(reasons) if reasons else "投票意欲が閾値に達せず"
        return False, reason

    return True, None


async def run_district_v10a(
    district_row: dict,
    candidates_by_district: dict,
    seed: int,
    personas_per_district: int,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
    calibration_strength: float,
    enable_calibration: bool,
    global_semaphore: asyncio.Semaphore | None = None,
    political_climate: dict | None = None,
):
    """1選挙区のv10aシミュレーション"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
    district_name = district_row.get("選挙区", district_id)

    logger.info(f"選挙区開始: {district_name} ({district_id})")

    # ペルソナ生成（人口統計ベース）
    personas = generate_demographic_personas_for_district(
        district_row, personas_per_district, seed
    )

    # 候補者データ
    candidates = candidates_by_district.get(district_id, [])
    if not candidates:
        alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
        candidates = candidates_by_district.get(alt_id, [])

    if not candidates:
        logger.warning(f"  候補者データなし: {district_id}")
        return None

    # ===== Stage 1: ルールベース投票率判定 =====
    rng = random.Random(seed + hash(district_id))
    weather_mod = get_weather_modifier(district_id)

    voting_personas = []
    abstaining_decisions = []

    for persona in personas:
        will_vote, reason = determine_turnout_demographic(persona, weather_modifier=weather_mod, rng=rng)
        if will_vote:
            voting_personas.append(persona)
        else:
            abstaining_decisions.append(VoteDecision(
                persona_id=persona.persona_id,
                will_vote=False,
                abstention_reason=reason,
                swing_level="moderate",  # 人口統計ペルソナにはswing_tendencyがない
            ))

    logger.info(
        f"  Stage 1: {len(voting_personas)}/{len(personas)}名が投票 "
        f"(天候補正: {weather_mod:+.2f})"
    )

    if not voting_personas:
        logger.warning(f"  投票者なし: {district_id}")
        return None

    # ===== Stage 2: LLM投票先決定（投票者のみ） =====
    all_llm_decisions = [None] * len(voting_personas)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_batch(batch_start: int, batch_personas):
        async with semaphore:
            persona_dicts = [asdict(p) for p in batch_personas]
            weather_desc = get_weather_description(district_id)
            prompt = build_calibrated_batch_prompt(
                district_name=district_name,
                area_description=district_row.get("対象地域", ""),
                candidates=candidates,
                district_context=district_row,
                personas=persona_dicts,
                weather=weather_desc,
                political_climate=political_climate,
            )

            async def _call_api():
                return await call_openrouter_async(
                    model=model,
                    system_prompt=CALIBRATED_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    temperature=temperature,
                )

            for attempt in range(3):
                try:
                    # グローバルセマフォでAPI同時呼び出し数を制限
                    if global_semaphore is not None:
                        async with global_semaphore:
                            response = await _call_api()
                    else:
                        response = await _call_api()
                    decisions = parse_llm_response(response, batch_personas, candidates)

                    for j, decision in enumerate(decisions):
                        global_idx = batch_start + j
                        if global_idx < len(all_llm_decisions):
                            decision.will_vote = True
                            all_llm_decisions[global_idx] = decision

                    logger.info(
                        f"  Stage 2 バッチ {batch_start}-{batch_start + len(batch_personas) - 1}: "
                        f"{len(decisions)}件完了"
                    )
                    break
                except Exception as e:
                    logger.warning(f"  バッチ {batch_start} リトライ {attempt + 1}/3: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"  バッチ {batch_start} 失敗")

            await asyncio.sleep(1.0)

    tasks = []
    for i in range(0, len(voting_personas), batch_size):
        batch = voting_personas[i:i + batch_size]
        tasks.append(process_batch(i, batch))

    await asyncio.gather(*tasks)

    # LLM失敗分のフォールバック
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
                swing_level="moderate",
                score_breakdown={"method": "fallback"},
            ))
        else:
            llm_decisions.append(decision)

    # ===== Stage 3: 事後キャリブレーション =====
    if enable_calibration:
        calibrated_decisions = calibrate_decisions(
            llm_decisions,
            district_context=district_row,
            strength=calibration_strength,
            seed=seed,
        )
        logger.info(f"  Stage 3: キャリブレーション適用 (強度={calibration_strength})")
    else:
        calibrated_decisions = llm_decisions
        logger.info("  Stage 3: キャリブレーションなし")

    # 全決定を統合
    all_decisions = abstaining_decisions + calibrated_decisions

    # 集計
    result = aggregate_district_results(
        district_id=district_id,
        district_name=district_name,
        personas=personas,
        decisions=all_decisions,
        candidates=candidates,
    )

    logger.info(
        f"  完了: {district_name} 投票{len(voting_personas)}/{len(personas)}名 "
        f"当選: {result.winner} ({result.winner_party})"
    )

    return result, all_decisions


async def run_experiment(args):
    """v10a 実験実行"""
    global _weather_cache

    tag = "v10a_demographic_pilot" if args.mode == "pilot" else "v10a_demographic_full"
    if not args.calibration:
        tag = tag.replace("v10a", "v10a_nocal")

    logger.info("=" * 70)
    logger.info(f"v10a 人口統計ペルソナ + LLM投票実験: {tag}")
    logger.info(f"  モード: {args.mode}")
    logger.info(f"  シード: {args.seed}")
    logger.info(f"  モデル: {args.model}")
    logger.info(f"  温度: {args.temperature}")
    logger.info(f"  キャリブレーション: {'有効' if args.calibration else '無効'}")
    logger.info(f"  キャリブレーション強度: {args.calibration_strength}")
    logger.info(f"  ペルソナ生成: 人口統計ベース")
    logger.info(f"  記憶: なし（ベースライン）")
    logger.info(f"  天気プロバイダー: {args.weather_provider}")
    logger.info(f"  内閣支持率: {args.cabinet_approval:.0%}")
    logger.info(f"  自民党支持率: {args.ldp_support:.0%}")
    logger.info(f"  無党派自民傾斜: {args.swing_voter_ldp_lean:.0%}")
    logger.info("=" * 70)

    # 天気データ取得
    weather_service = WeatherService(
        provider=args.weather_provider,
        openweathermap_api_key=os.environ.get("OPENWEATHERMAP_API_KEY", ""),
        target_date=os.environ.get("WEATHER_TARGET_DATE"),
    )
    _weather_cache = await weather_service.fetch_all_prefectures()
    logger.info(f"天気データ取得完了: {len(_weather_cache)}都道府県")

    # データ読み込み
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

    # 選挙区レベル並列化
    global_api_semaphore = asyncio.Semaphore(args.max_api_concurrency)
    district_semaphore = asyncio.Semaphore(args.max_district_concurrency)
    completed_count = 0
    completed_lock = asyncio.Lock()
    total_districts = len(target_districts)

    async def run_one_district(idx, district_row):
        nonlocal completed_count
        async with district_semaphore:
            district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
            # political_climate の構築
            pc = dict(DEFAULT_POLITICAL_CLIMATE)
            pc["cabinet_approval_rate"] = args.cabinet_approval
            pc["ldp_support_rate"] = args.ldp_support
            pc["swing_voter_ldp_lean"] = args.swing_voter_ldp_lean

            result_tuple = await run_district_v10a(
                district_row=district_row,
                candidates_by_district=candidates_by_district,
                seed=args.seed,
                personas_per_district=args.personas,
                model=args.model,
                temperature=args.temperature,
                batch_size=args.batch_size,
                concurrency=args.concurrency,
                calibration_strength=args.calibration_strength,
                enable_calibration=args.calibration,
                global_semaphore=global_api_semaphore,
                political_climate=pc,
            )
            async with completed_lock:
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == total_districts:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"進捗: {completed_count}/{total_districts} 選挙区完了 "
                        f"({elapsed:.1f}秒経過)"
                    )
            return idx, district_id, result_tuple

    tasks = [
        run_one_district(i, row)
        for i, row in enumerate(target_districts)
    ]
    task_results = await asyncio.gather(*tasks)

    # 元の順序でソートして結果を格納
    task_results.sort(key=lambda x: x[0])
    for _, district_id, result_tuple in task_results:
        if result_tuple is not None:
            result, decisions = result_tuple
            results.append(result)
            all_decisions_by_district[district_id] = decisions

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

    _print_summary(results, experiment_id)
    return experiment_id


def _save_results(results, all_decisions, args, tag, duration):
    """結果をファイルに保存"""
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    version = "v10a" if args.calibration else "v10a_nocal"
    experiment_id = f"{version}_{now.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}"

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

    # LLM投票決定の詳細JSON
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
        "description": f"v10a 人口統計ペルソナ + LLM投票（記憶なし）({args.mode}, seed={args.seed})",
        "tags": [tag, f"seed{args.seed}", "demographic", "llm_calibrated", "no_memory"],
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
            "method": "demographic_llm_calibrated",
            "generator_type": "demographic",
            "calibration_enabled": args.calibration,
            "calibration_strength": args.calibration_strength,
            "memory_enabled": False,
            "political_climate": {
                "cabinet_approval_rate": args.cabinet_approval,
                "ldp_support_rate": args.ldp_support,
                "swing_voter_ldp_lean": args.swing_voter_ldp_lean,
            },
            "weather_provider": args.weather_provider,
            "weather_data": {
                code: {
                    "prefecture_name": w.prefecture_name,
                    "temperature": w.temperature,
                    "precipitation_mm": w.precipitation_mm,
                    "snowfall_cm": w.snowfall_cm,
                    "wind_speed_kmh": w.wind_speed_kmh,
                    "weather_description_ja": w.weather_description_ja,
                    "turnout_modifier": w.turnout_modifier,
                    "source": w.source,
                }
                for code, w in _weather_cache.items()
            } if _weather_cache else None,
        },
        "methodology": {
            "persona_generation": "人口統計データベース（国勢調査CSV直接サンプリング）",
            "stage1": "ルールベース投票率判定（年齢×属性×天候補正）",
            "stage2": "LLM投票先決定（全投票者、分布アンカリング付きプロンプト）",
            "stage3": f"事後キャリブレーション（強度={args.calibration_strength}）" if args.calibration else "なし",
            "memory": "なし（ベースライン）",
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

    # experiments/ にも保存
    exp_log_dir = EXPERIMENTS_DIR / tag
    exp_log_dir.mkdir(parents=True, exist_ok=True)
    with open(exp_log_dir / "experiment.json", "w", encoding="utf-8") as f:
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
        "method": "demographic_llm_calibrated",
        "generator_type": "demographic",
        "memory": False,
    }


def _print_summary(results, experiment_id):
    """サマリ表示"""
    summary = _build_summary(results)

    print(f"\n{'=' * 60}")
    print(f"実験完了: {experiment_id}")
    print(f"{'=' * 60}")
    print(f"  ペルソナ生成: 人口統計ベース")
    print(f"  記憶: なし（ベースライン）")
    print(f"  選挙区数: {summary['total_districts']}")
    print(f"  投票率: {summary['national_turnout_rate']:.1%}")
    print(f"  政党別議席 (SMD):")
    for party, seats in sorted(summary["smd_seats"].items(), key=lambda x: -x[1]):
        print(f"    {party}: {seats}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="v10a 人口統計ペルソナ + LLM投票実験（記憶なし）")
    parser.add_argument("--mode", choices=["pilot", "all"], default="pilot")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--personas", type=int, default=100)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--batch-size", type=int, default=15)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--no-calibration", dest="calibration", action="store_false",
        help="事後キャリブレーションを無効化",
    )
    parser.add_argument(
        "--calibration-strength", type=float, default=0.3,
        help="キャリブレーション強度 (0.0-1.0, default=0.3)",
    )
    parser.add_argument(
        "--max-district-concurrency", type=int, default=20,
        help="最大同時実行選挙区数 (default=20)",
    )
    parser.add_argument(
        "--max-api-concurrency", type=int, default=10,
        help="最大同時API呼び出し数 (default=10)",
    )
    parser.add_argument(
        "--weather-provider", type=str, default="open-meteo",
        choices=["open-meteo", "openweathermap", "static"],
        help="天気データプロバイダー (default=open-meteo)",
    )
    # 政治状況パラメータ
    parser.add_argument(
        "--cabinet-approval", type=float, default=0.65,
        help="内閣支持率 (0.0-1.0, default=0.65)",
    )
    parser.add_argument(
        "--ldp-support", type=float, default=0.38,
        help="自民党全国支持率 (0.0-1.0, default=0.38)",
    )
    parser.add_argument(
        "--swing-voter-ldp-lean", type=float, default=0.15,
        help="無党派層の自民傾斜率 (0.0-1.0, default=0.15)",
    )
    parser.set_defaults(calibration=True)
    args = parser.parse_args()

    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
