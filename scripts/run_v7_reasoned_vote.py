"""
v7a 理由付き投票シミュレーション（全289区）

各ペルソナに投票先と理由を自然言語で説明させ、出口調査のシミュレーションデータを生成する。
v4bとの違い: 投票理由の記述により多くのトークンを割き、定性分析に使えるデータを生成。

使い方:
  python scripts/run_v7_reasoned_vote.py --mode pilot --seed 42
  python scripts/run_v7_reasoned_vote.py --mode all --seed 42
"""

import asyncio
import argparse
import csv
import json
import logging
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.services.simulation.persona_generator import (
    Persona,
    generate_personas_for_district,
    load_archetype_config,
    load_candidates,
    load_district_data,
)
from backend.app.services.simulation.llm_voter import (
    call_openrouter_async,
    DEFAULT_MODEL,
)
from backend.app.services.simulation.result_aggregator import aggregate_district_results
from backend.app.services.simulation.validators import validate_results
from backend.app.services.simulation.vote_calculator import VoteDecision
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

REASONED_SYSTEM_PROMPT = """あなたは日本の衆議院選挙の出口調査シミュレーターです。
投票所を出てきた有権者（ペルソナ）にインタビューする設定で、
各ペルソナの投票行動と詳細な理由を生成してください。

出口調査のリアリティを重視:
- 投票した人: 候補者名、政党名、投票理由を詳しく（100-200文字）
- 棄権した人: 棄権の理由を詳しく（80-150文字）
- 比例投票で票割れした人: なぜ小選挙区と違う政党に入れたか
- 投票を迷った人: 最後まで迷った候補者・政党は誰か
- 前回選挙との変化: 前回と投票先を変えた場合はその理由

全てのペルソナについて具体的な理由を記述してください。
出力はJSON配列で返してください。"""


def build_reasoned_prompt(
    district_name: str,
    area_description: str,
    candidates: list[dict],
    district_context: dict,
    personas: list[dict],
) -> str:
    """理由付き投票プロンプト"""

    party_names = {
        "ldp": "自民党", "chudo": "中道改革連合", "ishin": "日本維新の会",
        "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
        "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
        "shamin": "社民党", "mirai": "チームみらい", "independent": "無所属",
        "komei": "公明党",
    }

    candidate_lines = []
    for c in candidates:
        party = party_names.get(c.get("party_id", ""), c.get("party_id", ""))
        status_map = {"incumbent": "現職", "former": "元職", "new": "新人", "current": "現職"}
        status = status_map.get(c.get("status", "new"), c.get("status", ""))
        wins = c.get("previous_wins", 0)
        dual = "（比例重複）" if c.get("dual_candidacy") == "true" else ""
        candidate_lines.append(
            f"  - {c['candidate_name']}（{party}、{status}、当選{wins}回）{dual}"
        )

    support_lines = []
    support_keys = [
        ("支持率_自民党", "自民"), ("支持率_立憲民主党", "中道改革連合"),
        ("支持率_維新", "維新"), ("支持率_国民民主党", "国民"),
        ("支持率_共産党", "共産"), ("支持率_れいわ", "れいわ"),
    ]
    for key, label in support_keys:
        val = district_context.get(key, 0)
        pct = round(float(val) * 100, 1)
        support_lines.append(f"{label}{pct}%")

    issues = [district_context.get(f"主要課題{i}", "") for i in range(1, 4)]
    issues = [i for i in issues if i]

    persona_lines = []
    for i, p in enumerate(personas, 1):
        concerns = "、".join(p.get("top_concerns", [])[:3])
        sources = "、".join(p.get("information_sources", [])[:2])
        persona_lines.append(
            f"  {i}. [{p['archetype_name_ja']}] {p['age']}歳{p['gender']}、{p['occupation']}、"
            f"関心:{concerns}、情報源:{sources}、支持傾向:{p.get('party_affinity', '支持なし')}、"
            f"政治関心:{p.get('political_engagement', '中')}、イデオロギー:{p.get('ideology', '中道')}"
        )

    prompt = f"""## 選挙区情報
選挙区: {district_name}
対象地域: {area_description}
都市化分類: {district_context.get('都市化分類', '')}
天候: 2月8日、{'大雪・厳しい寒さ' if district_context.get('都道府県', '') in ['北海道','青森県','秋田県','山形県','新潟県'] else '冬型の寒さ'}

## 候補者一覧
{chr(10).join(candidate_lines)}

## 選挙区の政治傾向
政党支持率: {', '.join(support_lines)}
浮動票率: {round(float(district_context.get('浮動票率', 0.3)) * 100, 1)}%
地域課題: {', '.join(issues)}

## 全国政治状況
- 首相: 高市早苗（自民党）、内閣支持率63-67%
- 与党: 自民+維新連立、300議席超の勢い
- 争点: 消費税減税、物価高、社会保険料、外交安全保障
- 真冬選挙（36年ぶり）

## 出口調査対象者（{len(personas)}名）
{chr(10).join(persona_lines)}

## タスク
上記{len(personas)}名の出口調査結果をシミュレーションしてください。

```json
[
  {{
    "persona_index": 1,
    "will_vote": true,
    "abstention_reason": null,
    "smd_vote": {{
      "candidate": "候補者名",
      "party": "政党名",
      "reason": "詳細な投票理由（100-200文字）",
      "hesitated_candidates": ["最後まで迷った候補者名（あれば）"],
      "changed_from_last_election": true,
      "change_reason": "前回からの変化理由（あれば、50-100文字）"
    }},
    "proportional_vote": {{
      "party": "政党名",
      "reason": "詳細な投票理由（100-200文字）",
      "split_ticket": false,
      "split_reason": "票割れの理由（あれば）"
    }},
    "confidence": 0.7,
    "overall_sentiment": "今回の選挙への感想（50-100文字）",
    "swing_factors": ["投票の決め手1", "決め手2"]
  }},
  ...
]
```

注意:
- will_vote=false の場合は、棄権理由を詳細に（80-150文字）
- split_ticket=true は小選挙区と比例で別政党に投票した場合"""

    return prompt


def parse_reasoned_response(
    response_text: str, personas: list[Persona], candidates: list[dict]
) -> tuple[list[VoteDecision], list[dict]]:
    """理由付き投票レスポンスをパース。VoteDecisionと詳細データの両方を返す"""

    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text.strip()
        start = json_str.find('[')
        end = json_str.rfind(']')
        if start >= 0 and end >= 0:
            json_str = json_str[start:end + 1]

    try:
        results = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSONパース失敗: {e}")
        return [], []

    candidate_party_map = {}
    party_name_to_id = {
        "自民党": "ldp", "中道改革連合": "chudo", "日本維新の会": "ishin",
        "国民民主党": "dpfp", "日本共産党": "jcp", "れいわ新選組": "reiwa",
        "参政党": "sansei", "減税日本": "genzei", "日本保守党": "hoshuto",
        "社民党": "shamin", "チームみらい": "mirai", "無所属": "independent",
        "公明党": "komei",
    }
    for c in candidates:
        candidate_party_map[c["candidate_name"]] = c.get("party_id", "independent")

    decisions = []
    detailed_data = []

    for item in results:
        idx = item.get("persona_index", 0) - 1
        if idx < 0 or idx >= len(personas):
            continue

        persona = personas[idx]
        will_vote = item.get("will_vote", True)

        if not will_vote:
            decisions.append(VoteDecision(
                persona_id=persona.persona_id,
                will_vote=False,
                abstention_reason=item.get("abstention_reason", "理由不明"),
                swing_level=persona.swing_tendency,
            ))
            detailed_data.append({
                "persona_id": persona.persona_id,
                "archetype": persona.archetype_id,
                "will_vote": False,
                "abstention_reason": item.get("abstention_reason", ""),
                "overall_sentiment": item.get("overall_sentiment", ""),
            })
            continue

        smd_vote = item.get("smd_vote") or {}
        prop_vote = item.get("proportional_vote") or {}

        smd_candidate = smd_vote.get("candidate", "")
        smd_party = candidate_party_map.get(smd_candidate, "")
        if not smd_party:
            smd_party_name = smd_vote.get("party", "")
            smd_party = party_name_to_id.get(smd_party_name, smd_party_name)

        prop_party_name = prop_vote.get("party", "")
        prop_party = party_name_to_id.get(prop_party_name, prop_party_name)
        if not prop_party:
            prop_party = smd_party

        decisions.append(VoteDecision(
            persona_id=persona.persona_id,
            will_vote=True,
            smd_candidate=smd_candidate,
            smd_party=smd_party,
            proportional_party=prop_party,
            confidence=item.get("confidence", 0.5),
            needs_llm=False,
            swing_level=persona.swing_tendency,
        ))

        detailed_data.append({
            "persona_id": persona.persona_id,
            "archetype": persona.archetype_id,
            "age": persona.age,
            "gender": persona.gender,
            "occupation": persona.occupation,
            "will_vote": True,
            "smd_candidate": smd_candidate,
            "smd_party": smd_party,
            "smd_reason": smd_vote.get("reason", ""),
            "hesitated_candidates": smd_vote.get("hesitated_candidates", []),
            "changed_from_last_election": smd_vote.get("changed_from_last_election", False),
            "change_reason": smd_vote.get("change_reason", ""),
            "proportional_party": prop_party,
            "proportional_reason": prop_vote.get("reason", ""),
            "split_ticket": prop_vote.get("split_ticket", False),
            "split_reason": prop_vote.get("split_reason", ""),
            "confidence": item.get("confidence", 0.5),
            "overall_sentiment": item.get("overall_sentiment", ""),
            "swing_factors": item.get("swing_factors", []),
        })

    return decisions, detailed_data


async def run_district_reasoned(
    district_row: dict,
    archetypes: list[dict],
    candidates_by_district: dict,
    seed: int,
    personas_per_district: int,
    model: str,
    temperature: float,
    batch_size: int = 10,  # 理由が長いので小さめ
    concurrency: int = 3,
):
    """1選挙区の理由付き投票シミュレーション"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
    district_name = district_row.get("選挙区", district_id)

    logger.info(f"理由付き投票開始: {district_name}")

    personas = generate_personas_for_district(
        district_row, archetypes, personas_per_district, seed
    )

    candidates = candidates_by_district.get(district_id, [])
    if not candidates:
        alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
        candidates = candidates_by_district.get(alt_id, [])

    if not candidates:
        return None

    all_decisions = [None] * len(personas)
    all_detailed = [None] * len(personas)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_batch(batch_start, batch_personas):
        async with semaphore:
            persona_dicts = [asdict(p) for p in batch_personas]
            prompt = build_reasoned_prompt(
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
                        system_prompt=REASONED_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        temperature=temperature,
                        max_tokens=6000,  # 理由記述のために多め
                    )
                    decisions, detailed = parse_reasoned_response(
                        response, batch_personas, candidates
                    )
                    for j, (dec, det) in enumerate(zip(decisions, detailed)):
                        global_idx = batch_start + j
                        if global_idx < len(personas):
                            all_decisions[global_idx] = dec
                            all_detailed[global_idx] = det

                    logger.info(f"  バッチ {batch_start}: {len(decisions)}件完了")
                    break
                except Exception as e:
                    logger.warning(f"  バッチ {batch_start} リトライ {attempt + 1}: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)

            await asyncio.sleep(1)

    tasks = []
    for i in range(0, len(personas), batch_size):
        batch = personas[i:i + batch_size]
        tasks.append(process_batch(i, batch))

    await asyncio.gather(*tasks)

    # フォールバック
    final_decisions = []
    final_detailed = []
    for i in range(len(personas)):
        if all_decisions[i] is None:
            final_decisions.append(VoteDecision(
                persona_id=personas[i].persona_id,
                will_vote=False,
                abstention_reason="LLM処理失敗",
                swing_level=personas[i].swing_tendency,
            ))
            final_detailed.append({"persona_id": personas[i].persona_id, "will_vote": False, "error": True})
        else:
            final_decisions.append(all_decisions[i])
            final_detailed.append(all_detailed[i] or {})

    result = aggregate_district_results(
        district_id=district_id,
        district_name=district_name,
        personas=personas,
        decisions=final_decisions,
        candidates=candidates,
    )

    voted = sum(1 for d in final_decisions if d.will_vote)
    logger.info(f"  完了: {district_name} 投票{voted}/{len(personas)} 当選: {result.winner} ({result.winner_party})")

    return result, final_decisions, final_detailed


async def run_experiment(args):
    """v7a 実験実行"""
    tag = "v7a_reasoned_pilot" if args.mode == "pilot" else "v7a_reasoned_full"

    logger.info("=" * 70)
    logger.info(f"v7a 理由付き投票シミュレーション: {tag}")
    logger.info(f"  モード: {args.mode}")
    logger.info(f"  シード: {args.seed}")
    logger.info("=" * 70)

    config = load_archetype_config()
    archetypes = config["persona_archetypes"]
    districts = load_district_data()
    candidates_by_district = load_candidates()

    if args.mode == "pilot":
        target_ids = set(PILOT_DISTRICTS)
        target_districts = [d for d in districts
                           if f"{d['都道府県コード'].zfill(2)}_{d['区番号']}" in target_ids]
    else:
        target_districts = districts

    start_time = time.time()
    results = []
    all_detailed_data = {}

    for i, district_row in enumerate(target_districts):
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"

        result_tuple = await run_district_reasoned(
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

        if result_tuple:
            result, decisions, detailed = result_tuple
            results.append(result)
            all_detailed_data[district_id] = detailed

        if (i + 1) % 10 == 0:
            logger.info(f"進捗: {i + 1}/{len(target_districts)}区完了")

    duration = time.time() - start_time

    # 結果保存
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    experiment_id = f"v7a_{now.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}"

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
                "district_id": r.district_id, "district_name": r.district_name,
                "total_personas": r.total_personas, "turnout_count": r.turnout_count,
                "turnout_rate": r.turnout_rate, "winner": r.winner,
                "winner_party": r.winner_party, "winner_votes": r.winner_votes,
                "runner_up": r.runner_up, "runner_up_party": r.runner_up_party,
                "runner_up_votes": r.runner_up_votes, "margin": r.margin,
            })

    # 出口調査詳細データ（本実験の主出力）
    exit_poll_path = exp_dir / "exit_poll_data.json"
    with open(exit_poll_path, "w", encoding="utf-8") as f:
        json.dump(all_detailed_data, f, ensure_ascii=False, indent=2)

    # メタデータ
    party_seats = {}
    total_turnout = sum(r.turnout_count for r in results)
    total_personas = sum(r.total_personas for r in results)
    for r in results:
        if r.winner_party:
            party_seats[r.winner_party] = party_seats.get(r.winner_party, 0) + 1

    metadata = {
        "experiment_id": experiment_id,
        "created_at": now.isoformat(),
        "status": "completed",
        "duration_seconds": round(duration, 2),
        "description": f"v7a 理由付き投票シミュレーション ({args.mode}, seed={args.seed})",
        "tags": [tag, f"seed{args.seed}", "llm_reasoned_vote", "exit_poll"],
        "parameters": {
            "seed": args.seed, "personas_per_district": args.personas,
            "model": args.model, "temperature": args.temperature,
            "batch_size": args.batch_size, "concurrency": args.concurrency,
            "mode": args.mode, "district_count": len(results),
            "method": "llm_reasoned_vote",
        },
        "results_summary": {
            "national_turnout_rate": round(total_turnout / total_personas, 4) if total_personas else 0,
            "smd_seats": party_seats,
        },
    }
    with open(exp_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    exp_log_dir = EXPERIMENTS_DIR / tag
    exp_log_dir.mkdir(parents=True, exist_ok=True)
    with open(exp_log_dir / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"\n完了: {experiment_id} ({duration:.1f}秒)")
    logger.info(f"投票率: {round(total_turnout / total_personas, 4) if total_personas else 0:.1%}")
    for party, seats in sorted(party_seats.items(), key=lambda x: -x[1]):
        logger.info(f"  {party}: {seats}議席")
    logger.info(f"出口調査データ: {exit_poll_path}")


def main():
    parser = argparse.ArgumentParser(description="v7a 理由付き投票シミュレーション")
    parser.add_argument("--mode", choices=["pilot", "all"], default="all")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--personas", type=int, default=100)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
