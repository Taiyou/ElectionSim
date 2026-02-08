"""
v10a 欠落12地区の補完実験

2022年区割り変更で新設された12地区のv10aシミュレーションを実行し、
既存の277地区の結果と統合して289地区の完全な結果を生成する。

使い方:
  python scripts/run_v10a_missing_12.py
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# プロジェクトルートをパスに追加
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.run_v10a_demographic import (
    run_district_v10a,
    _save_proportional,
    _build_summary,
    _print_summary,
)
from backend.app.services.simulation.demographic_persona_generator import (
    load_district_data,
    load_candidates,
)
from backend.app.services.simulation.llm_voter import DEFAULT_MODEL
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

# 欠落12地区（2022年新設地区）
MISSING_DISTRICTS = [
    "11_16",  # 埼玉県16区
    "12_14",  # 千葉県14区
    "13_26",  # 東京都26区
    "13_27",  # 東京都27区
    "13_28",  # 東京都28区
    "13_29",  # 東京都29区
    "13_30",  # 東京都30区
    "14_18",  # 神奈川県18区
    "14_19",  # 神奈川県19区
    "14_20",  # 神奈川県20区
    "23_16",  # 愛知県16区
    "47_4",   # 沖縄県4区
]

# 元の実験と同じパラメータ
SEED = 42
PERSONAS_PER_DISTRICT = 100
MODEL = "deepseek/deepseek-chat"
TEMPERATURE = 0.7
BATCH_SIZE = 15
CONCURRENCY = 3
CALIBRATION_STRENGTH = 0.3
ENABLE_CALIBRATION = True
MAX_API_CONCURRENCY = 10
MAX_DISTRICT_CONCURRENCY = 12  # 12地区全部並列

# 統合先の既存実験
EXISTING_EXPERIMENT = "v10a_20260208_192948_seed42"


async def run_missing_districts():
    """欠落12地区のシミュレーション実行"""

    logger.info("=" * 70)
    logger.info("v10a 欠落12地区の補完実験")
    logger.info(f"  対象地区: {len(MISSING_DISTRICTS)}区")
    logger.info(f"  シード: {SEED}")
    logger.info(f"  モデル: {MODEL}")
    logger.info(f"  統合先: {EXISTING_EXPERIMENT}")
    logger.info("=" * 70)

    # データ読み込み
    districts = load_district_data()
    candidates_by_district = load_candidates()

    # 対象地区のフィルタリング
    target_ids = set(MISSING_DISTRICTS)
    target_districts = []
    for d in districts:
        district_id = f"{d['都道府県コード'].zfill(2)}_{d['区番号']}"
        if district_id in target_ids:
            target_districts.append(d)

    logger.info(f"  persona dataから{len(target_districts)}地区を検出")

    if len(target_districts) != 12:
        missing = target_ids - {
            f"{d['都道府県コード'].zfill(2)}_{d['区番号']}" for d in target_districts
        }
        logger.error(f"  persona dataに見つからない地区: {missing}")
        return

    # 候補者データの確認
    for d in target_districts:
        district_id = f"{d['都道府県コード'].zfill(2)}_{d['区番号']}"
        cands = candidates_by_district.get(district_id, [])
        if not cands:
            alt_id = f"{int(d['都道府県コード'])}_{d['区番号']}"
            cands = candidates_by_district.get(alt_id, [])
        logger.info(f"  {district_id}: 候補者{len(cands)}名")

    start_time = time.time()

    # 実行
    global_api_semaphore = asyncio.Semaphore(MAX_API_CONCURRENCY)
    district_semaphore = asyncio.Semaphore(MAX_DISTRICT_CONCURRENCY)

    results = []
    all_decisions_by_district = {}

    async def run_one(idx, district_row):
        async with district_semaphore:
            district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
            result_tuple = await run_district_v10a(
                district_row=district_row,
                candidates_by_district=candidates_by_district,
                seed=SEED,
                personas_per_district=PERSONAS_PER_DISTRICT,
                model=MODEL,
                temperature=TEMPERATURE,
                batch_size=BATCH_SIZE,
                concurrency=CONCURRENCY,
                calibration_strength=CALIBRATION_STRENGTH,
                enable_calibration=ENABLE_CALIBRATION,
                global_semaphore=global_api_semaphore,
            )
            return idx, district_id, result_tuple

    tasks = [run_one(i, row) for i, row in enumerate(target_districts)]
    task_results = await asyncio.gather(*tasks)

    task_results.sort(key=lambda x: x[0])
    for _, district_id, result_tuple in task_results:
        if result_tuple is not None:
            result, decisions = result_tuple
            results.append(result)
            all_decisions_by_district[district_id] = decisions

    duration = time.time() - start_time
    logger.info(f"\n12地区完了: {len(results)}区, {duration:.1f}秒")

    if len(results) != 12:
        logger.warning(f"  {12 - len(results)}地区が失敗しました")

    # --- 12地区のみの結果を保存 ---
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    supplement_id = f"v10a_supplement_{now.strftime('%Y%m%d_%H%M%S')}_seed{SEED}"
    supp_dir = RESULTS_DIR / supplement_id
    supp_dir.mkdir(parents=True, exist_ok=True)

    # CSV保存
    csv_path = supp_dir / "district_results.csv"
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

    # 決定詳細JSON
    decisions_data = {}
    for district_id, decisions in all_decisions_by_district.items():
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

    with open(supp_dir / "persona_decisions.json", "w", encoding="utf-8") as f:
        json.dump(decisions_data, f, ensure_ascii=False, indent=2)

    logger.info(f"12地区結果保存: {supp_dir}")

    # --- 既存277地区と統合 ---
    logger.info(f"\n既存実験 {EXISTING_EXPERIMENT} と統合中...")

    existing_dir = RESULTS_DIR / EXISTING_EXPERIMENT
    merged_id = f"v10a_merged_289_{now.strftime('%Y%m%d_%H%M%S')}_seed{SEED}"
    merged_dir = RESULTS_DIR / merged_id
    merged_dir.mkdir(parents=True, exist_ok=True)

    # 既存のdistrict_results.csv読み込み
    existing_csv = existing_dir / "district_results.csv"
    existing_rows = []
    with open(existing_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            existing_rows.append(row)

    # 新しい12地区の結果を追加
    for r in results:
        existing_rows.append({
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

    # district_idでソート
    existing_rows.sort(key=lambda x: (
        int(x["district_id"].split("_")[0]),
        int(x["district_id"].split("_")[1]),
    ))

    # 統合CSV書き出し
    merged_csv = merged_dir / "district_results.csv"
    with open(merged_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)

    # 既存のpersona_decisions.jsonと統合
    existing_decisions_path = existing_dir / "persona_decisions.json"
    with open(existing_decisions_path, "r", encoding="utf-8") as f:
        existing_decisions = json.load(f)

    existing_decisions.update(decisions_data)

    with open(merged_dir / "persona_decisions.json", "w", encoding="utf-8") as f:
        json.dump(existing_decisions, f, ensure_ascii=False, indent=2)

    # 統合用のsummary
    # resultsオブジェクトを再構築
    from backend.app.services.simulation.result_aggregator import DistrictResult
    all_results = []
    for row in existing_rows:
        # 既存のCSV行からDistrictResultに変換（proportional_votesは空dict）
        all_results.append(DistrictResult(
            district_id=row["district_id"],
            district_name=row["district_name"],
            total_personas=int(row["total_personas"]),
            turnout_count=int(row["turnout_count"]),
            turnout_rate=float(row["turnout_rate"]),
            winner=row["winner"],
            winner_party=row["winner_party"],
            winner_votes=int(row["winner_votes"]),
            runner_up=row["runner_up"],
            runner_up_party=row["runner_up_party"],
            runner_up_votes=int(row["runner_up_votes"]),
            margin=int(float(row["margin"])),
        ))

    summary = _build_summary(all_results)
    with open(merged_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 比例代表は既存のものをコピー
    existing_prop = existing_dir / "proportional_results.csv"
    if existing_prop.exists():
        import shutil
        shutil.copy2(existing_prop, merged_dir / "proportional_results.csv")

    # メタデータ
    metadata = {
        "experiment_id": merged_id,
        "created_at": now.isoformat(),
        "status": "completed",
        "duration_seconds": round(duration, 2),
        "description": f"v10a 289地区統合版（277既存 + 12地区補完）(seed={SEED})",
        "tags": ["v10a_merged_289", f"seed{SEED}", "demographic", "llm_calibrated", "no_memory"],
        "parameters": {
            "seed": SEED,
            "personas_per_district": PERSONAS_PER_DISTRICT,
            "model": str(MODEL),
            "temperature": TEMPERATURE,
            "batch_size": BATCH_SIZE,
            "concurrency": CONCURRENCY,
            "mode": "all_merged",
            "district_count": len(existing_rows),
            "total_personas": sum(int(r["total_personas"]) for r in existing_rows),
            "method": "demographic_llm_calibrated",
            "generator_type": "demographic",
            "calibration_enabled": ENABLE_CALIBRATION,
            "calibration_strength": CALIBRATION_STRENGTH,
            "memory_enabled": False,
        },
        "methodology": {
            "persona_generation": "人口統計データベース（国勢調査CSV直接サンプリング）",
            "stage1": "ルールベース投票率判定（年齢×属性×天候補正）",
            "stage2": "LLM投票先決定（全投票者、分布アンカリング付きプロンプト）",
            "stage3": f"事後キャリブレーション（強度={CALIBRATION_STRENGTH}）",
            "memory": "なし（ベースライン）",
            "note": f"277地区は{EXISTING_EXPERIMENT}から引用、12地区を追加実行して統合",
        },
        "results_summary": {
            "national_turnout_rate": summary["national_turnout_rate"],
            "smd_seats": summary["smd_seats"],
        },
        "source_experiments": {
            "existing_277": EXISTING_EXPERIMENT,
            "supplement_12": supplement_id,
        },
    }
    with open(merged_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"\n統合結果保存: {merged_dir}")
    logger.info(f"  総地区数: {len(existing_rows)}")
    logger.info(f"  政党別議席:")
    for party, seats in sorted(summary["smd_seats"].items(), key=lambda x: -x[1]):
        logger.info(f"    {party}: {seats}")

    print(f"\n{'=' * 60}")
    print(f"補完実験完了")
    print(f"{'=' * 60}")
    print(f"  12地区結果: {supp_dir}")
    print(f"  289地区統合: {merged_dir}")
    print(f"  政党別議席 (SMD, 289地区):")
    for party, seats in sorted(summary["smd_seats"].items(), key=lambda x: -x[1]):
        print(f"    {party}: {seats}")
    print(f"  投票率: {summary['national_turnout_rate']:.1%}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(run_missing_districts())
