"""
v10b 人口統計ペルソナ + 記憶付きLLM投票実験

v10aと同じ3ステージパイプラインに加えて、以下の記憶コンテキストをLLMに注入する:
1. 実選挙記憶: 2021衆院・2022参院・2024衆院・2025参院の結果
2. 経済状況記憶: 2026年1月時点の最新経済指標
3. エピソード記憶: 過去のシミュレーション結果（2回目以降）
4. キャリブレーション記憶: LLMバイアスの補正シグナル（2回目以降）

使い方:
  # 1回目（実データ記憶のみ）
  python scripts/run_v10b_memory.py --mode pilot --seed 42

  # 2回目（エピソード記憶＋キャリブレーション記憶が蓄積）
  python scripts/run_v10b_memory.py --mode pilot --seed 43

  # 記憶リセット
  python scripts/run_v10b_memory.py --reset-memory

  # 全289区
  python scripts/run_v10b_memory.py --mode all --seed 42
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
from backend.app.services.simulation.memory.memory_llm_voter import (
    MEMORY_SYSTEM_PROMPT,
    build_memory_augmented_prompt,
)
from backend.app.services.simulation.memory.store import MemoryStore
from backend.app.services.simulation.result_aggregator import (
    aggregate_district_results,
    calibrate_decisions,
    compute_calibration_signals,
)
from backend.app.services.simulation.vote_calculator import VoteDecision
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

WEATHER_MODIFIERS = {
    "01": -0.10, "02": -0.08, "03": -0.05, "05": -0.08,
    "06": -0.07, "07": -0.04, "15": -0.07, "16": -0.05,
    "17": -0.05, "18": -0.05, "19": -0.03, "20": -0.04,
    "04": -0.03, "08": -0.02, "09": -0.02, "10": -0.02,
}


def get_weather_modifier(district_id: str) -> float:
    pref_code = district_id.split("_")[0]
    return WEATHER_MODIFIERS.get(pref_code, -0.02)


def determine_turnout_demographic(
    persona: DemographicPersona,
    weather_modifier: float = 0.0,
    rng: random.Random | None = None,
) -> tuple[bool, str | None]:
    """人口統計ペルソナの投票/棄権をルールベースで判定"""
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


async def run_district_v10b(
    district_row: dict,
    candidates_by_district: dict,
    memory_context: str,
    seed: int,
    personas_per_district: int,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
    calibration_strength: float,
    enable_calibration: bool,
    global_semaphore: asyncio.Semaphore | None = None,
):
    """1選挙区のv10bシミュレーション（記憶付き）"""

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

    # 記憶コンテキスト
    if memory_context:
        logger.info(f"  記憶コンテキスト: {len(memory_context)}文字")
    else:
        logger.info("  記憶コンテキスト: なし（初回実行）")

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
                swing_level="moderate",
            ))

    logger.info(
        f"  Stage 1: {len(voting_personas)}/{len(personas)}名が投票 "
        f"(天候補正: {weather_mod:+.2f})"
    )

    if not voting_personas:
        logger.warning(f"  投票者なし: {district_id}")
        return None

    # ===== Stage 2: LLM投票先決定（記憶付きプロンプト） =====
    all_llm_decisions = [None] * len(voting_personas)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_batch(batch_start: int, batch_personas):
        async with semaphore:
            persona_dicts = [asdict(p) for p in batch_personas]

            # 記憶付きプロンプトを構築
            prompt = build_memory_augmented_prompt(
                district_name=district_name,
                area_description=district_row.get("対象地域", ""),
                candidates=candidates,
                district_context=district_row,
                personas=persona_dicts,
                memory_context=memory_context,
            )

            async def _call_api():
                return await call_openrouter_async(
                    model=model,
                    system_prompt=MEMORY_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    temperature=temperature,
                )

            for attempt in range(3):
                try:
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
    """v10b 実験実行"""

    tag = "v10b_memory_pilot" if args.mode == "pilot" else "v10b_memory_full"
    if not args.calibration:
        tag = tag.replace("v10b", "v10b_nocal")

    logger.info("=" * 70)
    logger.info(f"v10b 人口統計ペルソナ + 記憶付きLLM投票実験: {tag}")
    logger.info(f"  モード: {args.mode}")
    logger.info(f"  シード: {args.seed}")
    logger.info(f"  モデル: {args.model}")
    logger.info(f"  温度: {args.temperature}")
    logger.info(f"  キャリブレーション: {'有効' if args.calibration else '無効'}")
    logger.info(f"  キャリブレーション強度: {args.calibration_strength}")
    logger.info(f"  ペルソナ生成: 人口統計ベース")
    logger.info(f"  記憶: 有効（実データ + エピソード + キャリブレーション）")
    logger.info("=" * 70)

    # 記憶ストア初期化
    memory_store = MemoryStore()
    logger.info(f"  記憶DB: {memory_store.db_path}")

    # 既存の記憶情報を表示
    import sqlite3
    with sqlite3.connect(memory_store.db_path) as conn:
        episode_count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        cal_count = conn.execute("SELECT COUNT(*) FROM calibration_signals").fetchone()[0]
    logger.info(f"  既存エピソード数: {episode_count}, キャリブレーション信号数: {cal_count}")

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

    # 実験ID生成
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    version = "v10b" if args.calibration else "v10b_nocal"
    experiment_id = f"{version}_{now.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}"

    start_time = time.time()
    results = []
    all_decisions_by_district = {}

    # Phase 1: 記憶コンテキストを事前取得（全選挙区で同じ記憶状態を参照）
    memory_contexts = {}
    for district_row in target_districts:
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        memory_contexts[district_id] = memory_store.get_memory_context_for_prompt(district_id)

    # Phase 2: 全選挙区を並列実行
    global_api_semaphore = asyncio.Semaphore(args.max_api_concurrency)
    district_semaphore = asyncio.Semaphore(args.max_district_concurrency)
    completed_count = 0
    completed_lock = asyncio.Lock()
    total_districts = len(target_districts)

    async def run_one_district(idx, district_row):
        nonlocal completed_count
        async with district_semaphore:
            district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
            result_tuple = await run_district_v10b(
                district_row=district_row,
                candidates_by_district=candidates_by_district,
                memory_context=memory_contexts[district_id],
                seed=args.seed,
                personas_per_district=args.personas,
                model=args.model,
                temperature=args.temperature,
                batch_size=args.batch_size,
                concurrency=args.concurrency,
                calibration_strength=args.calibration_strength,
                enable_calibration=args.calibration,
                global_semaphore=global_api_semaphore,
            )
            async with completed_lock:
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == total_districts:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"進捗: {completed_count}/{total_districts} 選挙区完了 "
                        f"({elapsed:.1f}秒経過)"
                    )
            return idx, district_id, district_row, result_tuple

    tasks = [
        run_one_district(i, row)
        for i, row in enumerate(target_districts)
    ]
    task_results = await asyncio.gather(*tasks)

    # 元の順序でソートして結果を格納
    task_results.sort(key=lambda x: x[0])
    for _, district_id, district_row, result_tuple in task_results:
        if result_tuple is not None:
            result, decisions = result_tuple
            results.append(result)
            all_decisions_by_district[district_id] = decisions

    # Phase 3: 記憶をバッチ書き込み（逐次）
    logger.info("記憶の一括保存を開始...")
    for _, district_id, district_row, result_tuple in task_results:
        if result_tuple is not None:
            result, all_decisions = result_tuple
            # 政党別得票率を算出
            voted_decisions = [d for d in all_decisions if d.will_vote and d.smd_party]
            total_voted = len(voted_decisions)
            party_vote_shares = {}
            if total_voted > 0:
                counts: dict[str, int] = {}
                for d in voted_decisions:
                    counts[d.smd_party] = counts.get(d.smd_party, 0) + 1
                party_vote_shares = {p: round(c / total_voted, 4) for p, c in counts.items()}

            memory_store.store_episode(
                experiment_id=experiment_id,
                district_id=district_id,
                total_personas=result.total_personas,
                turnout_rate=result.turnout_rate,
                winner_party=result.winner_party,
                party_vote_shares=party_vote_shares,
                method="llm_demographic_memory",
                calibration_strength=args.calibration_strength if args.calibration else 0.0,
            )

            cal_signals = compute_calibration_signals(all_decisions, district_row)
            for sig in cal_signals:
                memory_store.store_calibration_signal(
                    district_id=district_id,
                    party_id=sig["party_id"],
                    target_share=sig["target_share"],
                    predicted_share=sig["predicted_share"],
                    experiment_id=experiment_id,
                )

            memory_store.update_trends(district_id)

    duration = time.time() - start_time
    logger.info(f"\n全選挙区完了: {len(results)}区, {duration:.1f}秒")

    # 記憶の最終状態を表示
    with sqlite3.connect(memory_store.db_path) as conn:
        episode_count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        cal_count = conn.execute("SELECT COUNT(*) FROM calibration_signals").fetchone()[0]
    logger.info(f"  記憶保存完了: エピソード{episode_count}件, キャリブレーション信号{cal_count}件")

    # 結果保存
    _save_results(
        results=results,
        all_decisions=all_decisions_by_district,
        args=args,
        tag=tag,
        duration=duration,
        experiment_id=experiment_id,
        now=now,
    )

    _print_summary(results, experiment_id)
    return experiment_id


def _save_results(results, all_decisions, args, tag, duration, experiment_id, now):
    """結果をファイルに保存"""
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
        "description": f"v10b 人口統計ペルソナ + 記憶付きLLM投票({args.mode}, seed={args.seed})",
        "tags": [tag, f"seed{args.seed}", "demographic", "llm_calibrated", "with_memory"],
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
            "method": "demographic_llm_memory",
            "generator_type": "demographic",
            "calibration_enabled": args.calibration,
            "calibration_strength": args.calibration_strength,
            "memory_enabled": True,
            "memory_layers": ["real_elections", "economic_context", "episodes", "calibration"],
        },
        "methodology": {
            "persona_generation": "人口統計データベース（国勢調査CSV直接サンプリング）",
            "stage1": "ルールベース投票率判定（年齢×属性×天候補正）",
            "stage2": "記憶付きLLM投票先決定（実選挙データ＋経済指標＋エピソード記憶＋キャリブレーション補正）",
            "stage3": f"事後キャリブレーション（強度={args.calibration_strength}）" if args.calibration else "なし",
            "memory": "4層（実選挙・経済状況・エピソード・キャリブレーション）",
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
        "method": "demographic_llm_memory",
        "generator_type": "demographic",
        "memory": True,
    }


def _print_summary(results, experiment_id):
    """サマリ表示"""
    summary = _build_summary(results)

    print(f"\n{'=' * 60}")
    print(f"実験完了: {experiment_id}")
    print(f"{'=' * 60}")
    print(f"  ペルソナ生成: 人口統計ベース")
    print(f"  記憶: 有効（実選挙＋経済＋エピソード＋キャリブレーション）")
    print(f"  選挙区数: {summary['total_districts']}")
    print(f"  投票率: {summary['national_turnout_rate']:.1%}")
    print(f"  政党別議席 (SMD):")
    for party, seats in sorted(summary["smd_seats"].items(), key=lambda x: -x[1]):
        print(f"    {party}: {seats}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="v10b 人口統計ペルソナ + 記憶付きLLM投票実験")
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
        "--reset-memory", action="store_true",
        help="記憶をリセットして終了",
    )
    parser.add_argument(
        "--max-district-concurrency", type=int, default=20,
        help="最大同時実行選挙区数 (default=20)",
    )
    parser.add_argument(
        "--max-api-concurrency", type=int, default=10,
        help="最大同時API呼び出し数 (default=10)",
    )
    parser.set_defaults(calibration=True)
    args = parser.parse_args()

    if args.reset_memory:
        store = MemoryStore()
        store.reset()
        logger.info("記憶をリセットしました")
        return

    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
