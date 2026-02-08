"""
v5a ペルソナ間議論シミュレーション（パイロット10区）

同じ選挙区の5人のペルソナをグループにし、3ターンの議論を行った後に投票させる。
SNS/井戸端会議での情報交換・説得の影響をモデル化する。

使い方:
  python scripts/run_v5_discussion.py --seed 42
"""

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
from backend.app.services.simulation.validators import validate_results
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

DISCUSSION_SYSTEM_PROMPT = """あなたは日本の衆議院選挙に関する有権者グループの会話シミュレーターです。
与えられた5人のペルソナの属性を忠実に再現し、彼らが投票について話し合う自然な会話を生成してください。

ルール:
- 各ペルソナの年齢、職業、政治関心度、支持傾向に沿った発言をさせること
- 政治関心が低い人は短い発言、高い人は具体的な政策に言及
- 意見が合う場面、対立する場面の両方を自然に含めること
- SNS的な軽い雑談から始まり、徐々に具体的な候補者・政策の話題に移行
- 各ターンは5人全員が1回ずつ発言（合計5発言/ターン）
- 出力はJSON形式で"""

VOTE_AFTER_DISCUSSION_PROMPT = """あなたは日本の衆議院選挙の有権者投票シミュレーターです。
以下のグループ議論を経た5人のペルソナが、最終的にどのような投票行動を取るかを予測してください。

重要: 議論の内容がペルソナの投票判断に影響を与えることをリアルに反映してください。
- 説得力のある意見に触れて考えが変わるペルソナ
- 議論しても考えが変わらないペルソナ
- 議論で投票意欲が上がった/下がったペルソナ

出力はJSON配列で返してください。"""


def build_discussion_prompt(
    district_name: str,
    candidates: list[dict],
    district_context: dict,
    group_personas: list[Persona],
    turn: int,
    previous_discussion: str = "",
) -> str:
    """議論プロンプトを構築"""

    party_names = {
        "ldp": "自民党", "chudo": "中道改革連合", "ishin": "日本維新の会",
        "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
        "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
        "shamin": "社民党", "mirai": "チームみらい", "independent": "無所属",
    }

    candidate_lines = []
    for c in candidates:
        status_map = {"incumbent": "現職", "former": "元職", "new": "新人", "current": "現職"}
        party = party_names.get(c.get("party_id", ""), c.get("party_id", ""))
        status = status_map.get(c.get("status", "new"), c.get("status", ""))
        candidate_lines.append(f"  - {c['candidate_name']}（{party}、{status}）")

    persona_lines = []
    for i, p in enumerate(group_personas, 1):
        concerns = "、".join(p.top_concerns[:3])
        persona_lines.append(
            f"  {i}. 「{p.archetype_name_ja}」 {p.age}歳{p.gender}、{p.occupation}、"
            f"関心:{concerns}、支持傾向:{p.party_affinity}、"
            f"政治関心:{p.political_engagement}"
        )

    prev_section = ""
    if previous_discussion:
        prev_section = f"\n## これまでの議論\n{previous_discussion}\n"

    prompt = f"""## 選挙区: {district_name}

## 候補者
{chr(10).join(candidate_lines)}

## 全国情勢
- 2026年2月8日投開票、高市早苗首相（自民）、自維連立で300議席超の勢い
- 真冬選挙、消費税減税・物価高が争点

## グループメンバー
{chr(10).join(persona_lines)}
{prev_section}
## タスク（ターン{turn}/3）
5人が選挙について{'話し始めます' if turn == 1 else '議論を続けます'}。
{'まずは軽い話題から入ってください。' if turn == 1 else ''}
{'より具体的な候補者・政策の話に踏み込んでください。' if turn == 2 else ''}
{'最後のまとめ。投票日に向けた最終的な意見交換です。' if turn == 3 else ''}

以下のJSON形式で出力してください:
```json
{{
  "turn": {turn},
  "statements": [
    {{"persona_index": 1, "statement": "発言内容（50-200文字）", "sentiment": "positive/negative/neutral", "influenced_by": null}},
    {{"persona_index": 2, "statement": "...", "sentiment": "...", "influenced_by": 1}},
    ...
  ]
}}
```"""

    return prompt


def build_vote_after_discussion_prompt(
    district_name: str,
    candidates: list[dict],
    district_context: dict,
    group_personas: list[Persona],
    full_discussion: str,
) -> str:
    """議論後の投票プロンプト"""

    party_names = {
        "ldp": "自民党", "chudo": "中道改革連合", "ishin": "日本維新の会",
        "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
        "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
        "shamin": "社民党", "mirai": "チームみらい", "independent": "無所属",
    }

    candidate_lines = []
    for c in candidates:
        status_map = {"incumbent": "現職", "former": "元職", "new": "新人", "current": "現職"}
        party = party_names.get(c.get("party_id", ""), c.get("party_id", ""))
        status = status_map.get(c.get("status", "new"), c.get("status", ""))
        candidate_lines.append(f"  - {c['candidate_name']}（{party}、{status}）")

    persona_lines = []
    for i, p in enumerate(group_personas, 1):
        concerns = "、".join(p.top_concerns[:3])
        persona_lines.append(
            f"  {i}. 「{p.archetype_name_ja}」 {p.age}歳{p.gender}、{p.occupation}、"
            f"関心:{concerns}、支持傾向:{p.party_affinity}"
        )

    prompt = f"""## 選挙区: {district_name}

## 候補者
{chr(10).join(candidate_lines)}

## グループメンバー
{chr(10).join(persona_lines)}

## グループ議論の内容
{full_discussion}

## タスク
上記の議論を踏まえ、5人それぞれの最終的な投票行動を予測してください。
議論で意見が変わった人、変わらなかった人を明確に区別してください。

```json
[
  {{
    "persona_index": 1,
    "will_vote": true,
    "abstention_reason": null,
    "smd_vote": {{
      "candidate": "候補者名",
      "party": "政党名",
      "reason": "投票理由（議論の影響を含む、50-150文字）"
    }},
    "proportional_vote": {{
      "party": "政党名",
      "reason": "投票理由（50-150文字）"
    }},
    "confidence": 0.7,
    "discussion_impact": "議論で考えが変わった点（なければnull）",
    "swing_factors": ["決め手1", "決め手2"]
  }},
  ...
]
```"""

    return prompt


async def run_group_discussion(
    district_name: str,
    candidates: list[dict],
    district_context: dict,
    group_personas: list[Persona],
    model: str,
    temperature: float,
) -> tuple[str, list[dict]]:
    """1グループの3ターン議論を実行"""

    full_discussion = ""
    all_statements = []

    for turn in range(1, 4):
        prompt = build_discussion_prompt(
            district_name=district_name,
            candidates=candidates,
            district_context=district_context,
            group_personas=group_personas,
            turn=turn,
            previous_discussion=full_discussion,
        )

        response = await call_openrouter_async(
            model=model,
            system_prompt=DISCUSSION_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=temperature,
            max_tokens=2000,
        )

        # パース
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                turn_data = json.loads(json_match.group(1))
                statements = turn_data.get("statements", [])
                all_statements.extend(statements)

                # 議論テキストを累積
                for s in statements:
                    idx = s.get("persona_index", "?")
                    p = group_personas[idx - 1] if 1 <= idx <= len(group_personas) else None
                    name = f"{p.archetype_name_ja}({p.age}歳)" if p else f"ペルソナ{idx}"
                    full_discussion += f"[ターン{turn}] {name}: {s.get('statement', '')}\n"

            except json.JSONDecodeError:
                full_discussion += f"[ターン{turn}] (パース失敗)\n"
        else:
            full_discussion += f"[ターン{turn}] {response[:200]}\n"

        await asyncio.sleep(1)

    return full_discussion, all_statements


async def run_district_discussion(
    district_row: dict,
    archetypes: list[dict],
    candidates_by_district: dict,
    seed: int,
    personas_per_district: int,
    model: str,
    temperature: float,
    groups_per_district: int = 10,
    group_size: int = 5,
):
    """1選挙区の議論シミュレーション"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
    district_name = district_row.get("選挙区", district_id)

    logger.info(f"議論開始: {district_name}")

    # ペルソナ生成
    personas = generate_personas_for_district(
        district_row, archetypes, personas_per_district, seed
    )

    candidates = candidates_by_district.get(district_id, [])
    if not candidates:
        alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
        candidates = candidates_by_district.get(alt_id, [])

    if not candidates:
        logger.warning(f"  候補者データなし: {district_id}")
        return None

    # ペルソナをグループ分け（シャッフルして5人ずつ）
    rng = random.Random(seed + hash(district_id))
    indices = list(range(len(personas)))
    rng.shuffle(indices)

    all_decisions = [None] * len(personas)
    discussion_logs = []

    total_groups = min(groups_per_district, len(personas) // group_size)

    for g in range(total_groups):
        group_indices = indices[g * group_size:(g + 1) * group_size]
        group_personas = [personas[i] for i in group_indices]

        logger.info(f"  グループ {g + 1}/{total_groups} 議論中...")

        # 3ターン議論
        discussion_text, statements = await run_group_discussion(
            district_name=district_name,
            candidates=candidates,
            district_context=district_row,
            group_personas=group_personas,
            model=model,
            temperature=temperature,
        )

        # 議論後の投票
        vote_prompt = build_vote_after_discussion_prompt(
            district_name=district_name,
            candidates=candidates,
            district_context=district_row,
            group_personas=group_personas,
            full_discussion=discussion_text,
        )

        vote_response = await call_openrouter_async(
            model=model,
            system_prompt=VOTE_AFTER_DISCUSSION_PROMPT,
            user_prompt=vote_prompt,
            temperature=temperature,
        )

        group_decisions = parse_llm_response(vote_response, group_personas, candidates)

        # 結果をグローバルインデックスにマッピング
        for j, decision in enumerate(group_decisions):
            if j < len(group_indices):
                all_decisions[group_indices[j]] = decision

        discussion_logs.append({
            "group": g + 1,
            "persona_indices": group_indices,
            "discussion": discussion_text,
            "statements": statements,
        })

        await asyncio.sleep(1)

    # 議論に参加しなかったペルソナ（グループに入れなかった分）は棄権扱い
    final_decisions = []
    for i, decision in enumerate(all_decisions):
        if decision is None:
            final_decisions.append(VoteDecision(
                persona_id=personas[i].persona_id,
                will_vote=False,
                abstention_reason="議論グループ外（未処理）",
                swing_level=personas[i].swing_tendency,
            ))
        else:
            final_decisions.append(decision)

    # 集計
    result = aggregate_district_results(
        district_id=district_id,
        district_name=district_name,
        personas=personas,
        decisions=final_decisions,
        candidates=candidates,
    )

    voted = sum(1 for d in final_decisions if d.will_vote)
    logger.info(f"  完了: {district_name} 投票{voted}/{len(personas)} 当選: {result.winner} ({result.winner_party})")

    return result, final_decisions, discussion_logs


async def run_experiment(args):
    """v5a 実験実行"""
    logger.info("=" * 70)
    logger.info("v5a ペルソナ間議論シミュレーション")
    logger.info(f"  シード: {args.seed}")
    logger.info(f"  グループサイズ: {args.group_size}人")
    logger.info(f"  グループ数/選挙区: {args.groups}")
    logger.info(f"  議論ターン: 3")
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
    all_discussion_logs = {}

    for i, district_row in enumerate(target_districts):
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"

        result_tuple = await run_district_discussion(
            district_row=district_row,
            archetypes=archetypes,
            candidates_by_district=candidates_by_district,
            seed=args.seed,
            personas_per_district=args.personas,
            model=args.model,
            temperature=args.temperature,
            groups_per_district=args.groups,
            group_size=args.group_size,
        )

        if result_tuple is not None:
            result, decisions, logs = result_tuple
            results.append(result)
            all_discussion_logs[district_id] = logs

    duration = time.time() - start_time

    # 結果保存
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    experiment_id = f"v5a_{now.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}"

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

    # 議論ログ
    logs_path = exp_dir / "discussion_logs.json"
    with open(logs_path, "w", encoding="utf-8") as f:
        json.dump(all_discussion_logs, f, ensure_ascii=False, indent=2)

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
        "description": f"v5a ペルソナ間議論シミュレーション (seed={args.seed})",
        "tags": ["v5a_discussion", f"seed{args.seed}", "llm_discussion"],
        "parameters": {
            "seed": args.seed, "personas_per_district": args.personas,
            "model": args.model, "temperature": args.temperature,
            "group_size": args.group_size, "groups_per_district": args.groups,
            "discussion_turns": 3, "mode": "pilot",
            "district_count": len(results),
            "method": "llm_group_discussion",
        },
        "results_summary": {
            "national_turnout_rate": round(total_turnout / total_personas, 4) if total_personas else 0,
            "smd_seats": party_seats,
        },
    }
    with open(exp_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # experiments/ にログ
    exp_log_dir = EXPERIMENTS_DIR / "v5a_discussion"
    exp_log_dir.mkdir(parents=True, exist_ok=True)
    with open(exp_log_dir / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"\n完了: {experiment_id} ({duration:.1f}秒)")
    for party, seats in sorted(party_seats.items(), key=lambda x: -x[1]):
        logger.info(f"  {party}: {seats}議席")


def main():
    parser = argparse.ArgumentParser(description="v5a ペルソナ間議論シミュレーション")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--personas", type=int, default=100)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--group-size", type=int, default=5)
    parser.add_argument("--groups", type=int, default=10)
    args = parser.parse_args()

    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
