"""
v6a ニュース・イベント時系列反応シミュレーション（パイロット10区）

選挙期間中の5日間のイベントをペルソナに提示し、日ごとに支持が変動する過程をシミュレーション。

使い方:
  python scripts/run_v6_timeline.py --seed 42
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
    parse_llm_response,
    DEFAULT_MODEL,
)
from backend.app.services.simulation.result_aggregator import aggregate_district_results
from backend.app.services.simulation.vote_calculator import VoteDecision

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

# 選挙期間中の5日間イベントシナリオ
DAILY_EVENTS = [
    {
        "day": 1,
        "date": "2月4日（火）公示日",
        "events": [
            "自民・維新連立政権が消費税の食料品ゼロ税率を正式に選挙公約として発表",
            "中道改革連合が「教育完全無償化」と「最低賃金1500円」を掲げ対抗",
            "各選挙区で候補者が出揃い、選挙戦スタート",
        ],
        "media_tone": "自民優勢の報道が多い、野党は分裂気味と報じられる",
    },
    {
        "day": 2,
        "date": "2月5日（水）序盤情勢",
        "events": [
            "メディア各社の序盤情勢調査で自民+維新が300議席超の勢い",
            "SNSで「選挙に行っても意味がない」がトレンド入り",
            "れいわ新選組の山本太郎代表がYouTubeライブで若者向けアピール、100万再生突破",
        ],
        "media_tone": "自民圧勝予測に対する危機感が野党支持者に広がる",
    },
    {
        "day": 3,
        "date": "2月6日（木）中盤のサプライズ",
        "events": [
            "自民党の有力議員が政治資金問題で週刊誌に報じられ、SNSで炎上",
            "高市首相が「社会保険料の上限引き下げ」を追加公約として発表",
            "国民民主党が減税案の具体的な財源を提示し、経済界から評価",
        ],
        "media_tone": "自民にネガティブニュースが出るも、全体の勢いは変わらず",
    },
    {
        "day": 4,
        "date": "2月7日（金）投票前日",
        "events": [
            "気象庁が「2月8日は日本海側で大雪、太平洋側も広く冷え込み」と発表",
            "各党党首が最後の訴え、新宿・大阪・名古屋で街頭演説",
            "SNSで「期日前投票は今日まで！」がトレンド1位に",
            "高齢者施設での不在者投票が話題に",
        ],
        "media_tone": "投票率低下への懸念が強まる、特に若年層の棄権が心配される",
    },
    {
        "day": 5,
        "date": "2月8日（土）投票日当日",
        "events": [
            "北海道・東北・北陸で大雪、交通に影響",
            "関東以西は晴れるも厳しい冷え込み",
            "午前中の投票率は前回を下回るペース",
            "SNSで「投票に行こう」と「寒くて無理」が同時トレンド入り",
        ],
        "media_tone": "天候が投票行動に大きく影響する見込み",
    },
]

TIMELINE_SYSTEM_PROMPT = """あなたは日本の衆議院選挙における有権者の心理変化シミュレーターです。
選挙期間中の日々のニュース・イベントに対して、ペルソナがどのように反応し、
支持が変動するかを予測してください。

重要:
- ペルソナの情報源（SNS、テレビ、新聞等）によって、イベントへの感度が異なる
- 政治関心度が低い人は後半のイベントにしか反応しない傾向がある
- 高齢者はテレビの影響が大きく、若年層はSNSの影響が大きい
- 天候情報は投票日の行動に直接影響する"""


def build_timeline_prompt(
    district_name: str,
    candidates: list[dict],
    district_context: dict,
    personas: list[dict],
    events: list[dict],
    day: int,
) -> str:
    """時系列イベント反応プロンプト"""

    party_names = {
        "ldp": "自民党", "chudo": "中道改革連合", "ishin": "日本維新の会",
        "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
        "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
        "shamin": "社民党", "mirai": "チームみらい", "independent": "無所属",
    }

    candidate_lines = []
    for c in candidates:
        party = party_names.get(c.get("party_id", ""), c.get("party_id", ""))
        status_map = {"incumbent": "現職", "former": "元職", "new": "新人", "current": "現職"}
        status = status_map.get(c.get("status", "new"), c.get("status", ""))
        candidate_lines.append(f"  - {c['candidate_name']}（{party}、{status}）")

    persona_lines = []
    for i, p in enumerate(personas, 1):
        concerns = "、".join(p.get("top_concerns", [])[:3])
        sources = "、".join(p.get("information_sources", [])[:2])
        persona_lines.append(
            f"  {i}. [{p['archetype_name_ja']}] {p['age']}歳{p['gender']}、{p['occupation']}、"
            f"関心:{concerns}、情報源:{sources}、支持傾向:{p.get('party_affinity', '支持なし')}、"
            f"政治関心:{p.get('political_engagement', '中')}"
        )

    # 当日までのイベントを累積
    all_events_text = ""
    for event_day in events[:day]:
        all_events_text += f"\n### {event_day['date']}\n"
        for e in event_day["events"]:
            all_events_text += f"- {e}\n"
        all_events_text += f"メディアの論調: {event_day['media_tone']}\n"

    if day < 5:
        # 中間日: 現時点の支持傾向を返す
        task_text = f"""上記{len(personas)}名のペルソナが、{events[day-1]['date']}時点で
どのような支持傾向にあるかを予測してください。

```json
[
  {{
    "persona_index": 1,
    "current_leaning": "候補者名 or 未定",
    "leaning_party": "政党名 or 未定",
    "confidence": 0.5,
    "reaction_to_today": "今日のニュースへの反応（50-100文字）",
    "will_vote_likelihood": 0.7
  }},
  ...
]
```"""
    else:
        # 投票日: 最終投票行動を返す
        task_text = f"""投票日当日です。5日間のイベントを全て踏まえた上で、
{len(personas)}名の最終的な投票行動を予測してください。

```json
[
  {{
    "persona_index": 1,
    "will_vote": true,
    "abstention_reason": null,
    "smd_vote": {{
      "candidate": "候補者名",
      "party": "政党名",
      "reason": "5日間の情勢を踏まえた投票理由（50-150文字）"
    }},
    "proportional_vote": {{
      "party": "政党名",
      "reason": "投票理由（50-150文字）"
    }},
    "confidence": 0.7,
    "key_event": "最も影響を受けたイベント",
    "swing_factors": ["決め手1", "決め手2"]
  }},
  ...
]
```"""

    prompt = f"""## 選挙区: {district_name}

## 候補者
{chr(10).join(candidate_lines)}

## 選挙期間中のイベント（{events[day-1]['date']}まで）
{all_events_text}

## ペルソナ一覧（{len(personas)}名）
{chr(10).join(persona_lines)}

## タスク
{task_text}"""

    return prompt


async def run_district_timeline(
    district_row: dict,
    archetypes: list[dict],
    candidates_by_district: dict,
    seed: int,
    personas_per_district: int,
    model: str,
    temperature: float,
    batch_size: int = 15,
):
    """1選挙区の時系列シミュレーション"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
    district_name = district_row.get("選挙区", district_id)

    logger.info(f"時系列シミュレーション開始: {district_name}")

    personas = generate_personas_for_district(
        district_row, archetypes, personas_per_district, seed
    )

    candidates = candidates_by_district.get(district_id, [])
    if not candidates:
        alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
        candidates = candidates_by_district.get(alt_id, [])

    if not candidates:
        return None

    daily_results = []

    # 5日間のシミュレーション
    for day in range(1, 6):
        logger.info(f"  Day {day}: {DAILY_EVENTS[day - 1]['date']}")

        # バッチ処理
        day_responses = []
        for batch_start in range(0, len(personas), batch_size):
            batch = personas[batch_start:batch_start + batch_size]
            batch_dicts = [asdict(p) for p in batch]

            prompt = build_timeline_prompt(
                district_name=district_name,
                candidates=candidates,
                district_context=district_row,
                personas=batch_dicts,
                events=DAILY_EVENTS,
                day=day,
            )

            for attempt in range(3):
                try:
                    response = await call_openrouter_async(
                        model=model,
                        system_prompt=TIMELINE_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        temperature=temperature,
                    )
                    day_responses.append(response)
                    break
                except Exception as e:
                    logger.warning(f"    バッチ {batch_start} リトライ: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2)

            await asyncio.sleep(1)

        daily_results.append({
            "day": day,
            "date": DAILY_EVENTS[day - 1]["date"],
            "responses": day_responses,
        })

    # 最終日（Day 5）のレスポンスから投票行動をパース
    final_decisions = []
    for response_text in daily_results[-1]["responses"]:
        batch_decisions = parse_llm_response(response_text, personas, candidates)
        final_decisions.extend(batch_decisions)

    # 足りない分はフォールバック
    while len(final_decisions) < len(personas):
        idx = len(final_decisions)
        final_decisions.append(VoteDecision(
            persona_id=personas[idx].persona_id,
            will_vote=False,
            abstention_reason="時系列シミュレーション未処理",
            swing_level=personas[idx].swing_tendency,
        ))

    # 余分なものをカット
    final_decisions = final_decisions[:len(personas)]

    result = aggregate_district_results(
        district_id=district_id,
        district_name=district_name,
        personas=personas,
        decisions=final_decisions,
        candidates=candidates,
    )

    voted = sum(1 for d in final_decisions if d.will_vote)
    logger.info(f"  完了: {district_name} 投票{voted}/{len(personas)} 当選: {result.winner} ({result.winner_party})")

    return result, final_decisions, daily_results


async def run_experiment(args):
    """v6a 実験実行"""
    logger.info("=" * 70)
    logger.info("v6a ニュース・イベント時系列反応シミュレーション")
    logger.info(f"  シード: {args.seed}")
    logger.info(f"  イベント日数: 5")
    logger.info("=" * 70)

    config = load_archetype_config()
    archetypes = config["persona_archetypes"]
    districts = load_district_data()
    candidates_by_district = load_candidates()

    target_ids = set(PILOT_DISTRICTS)
    target_districts = [d for d in districts
                       if f"{d['都道府県コード'].zfill(2)}_{d['区番号']}" in target_ids]

    start_time = time.time()
    results = []
    all_timelines = {}

    for district_row in target_districts:
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"

        result_tuple = await run_district_timeline(
            district_row=district_row,
            archetypes=archetypes,
            candidates_by_district=candidates_by_district,
            seed=args.seed,
            personas_per_district=args.personas,
            model=args.model,
            temperature=args.temperature,
            batch_size=args.batch_size,
        )

        if result_tuple:
            result, decisions, timeline = result_tuple
            results.append(result)
            all_timelines[district_id] = timeline

    duration = time.time() - start_time

    # 結果保存
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    experiment_id = f"v6a_{now.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}"

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

    # タイムラインログ（レスポンス全文は大きいので要約版）
    timeline_summary = {}
    for district_id, timeline in all_timelines.items():
        timeline_summary[district_id] = [
            {"day": t["day"], "date": t["date"], "batch_count": len(t["responses"])}
            for t in timeline
        ]
    with open(exp_dir / "timeline_summary.json", "w", encoding="utf-8") as f:
        json.dump(timeline_summary, f, ensure_ascii=False, indent=2)

    # イベントシナリオ
    with open(exp_dir / "daily_events.json", "w", encoding="utf-8") as f:
        json.dump(DAILY_EVENTS, f, ensure_ascii=False, indent=2)

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
        "description": f"v6a 時系列イベント反応シミュレーション (seed={args.seed})",
        "tags": ["v6a_timeline", f"seed{args.seed}", "llm_timeline"],
        "parameters": {
            "seed": args.seed, "personas_per_district": args.personas,
            "model": args.model, "temperature": args.temperature,
            "batch_size": args.batch_size, "timeline_days": 5,
            "mode": "pilot", "district_count": len(results),
            "method": "llm_timeline_reaction",
        },
        "results_summary": {
            "national_turnout_rate": round(total_turnout / total_personas, 4) if total_personas else 0,
            "smd_seats": party_seats,
        },
    }
    with open(exp_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    exp_log_dir = EXPERIMENTS_DIR / "v6a_timeline"
    exp_log_dir.mkdir(parents=True, exist_ok=True)
    with open(exp_log_dir / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"\n完了: {experiment_id} ({duration:.1f}秒)")
    for party, seats in sorted(party_seats.items(), key=lambda x: -x[1]):
        logger.info(f"  {party}: {seats}議席")


def main():
    parser = argparse.ArgumentParser(description="v6a 時系列イベント反応シミュレーション")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--personas", type=int, default=100)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--batch-size", type=int, default=15)
    args = parser.parse_args()

    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
