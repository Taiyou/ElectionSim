"""
シミュレーションエンジン メインクラス

ハイブリッドアプローチ:
- Tier 1: ルールベース（低スイング層の投票先を確定）
- Tier 2: LLM（中〜高スイング層をバッチプロンプトでまとめて処理）
"""

import csv
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

from .persona_generator import (
    Persona,
    generate_personas_for_district,
    load_archetype_config,
    load_candidates,
    load_district_data,
)
from .vote_calculator import VoteDecision, calculate_vote
from .prompts import SYSTEM_PROMPT, build_batch_prompt
from .result_aggregator import aggregate_district_results, DistrictResult
from .validators import validate_results

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_DIR = BASE_DIR / "backend" / "app" / "data"


class SimulationEngine:
    """ペルソナ投票シミュレーションの実行エンジン"""

    def __init__(
        self,
        seed: int = 42,
        personas_per_district: int = 100,
        llm_batch_size: int = 15,
        model: str = "claude-sonnet-4-20250514",
        use_batch_api: bool = True,
        factor_weights: dict | None = None,
        swing_noise_offset: float = 0.0,
        independent_loyalty_score: float = 0.3,
        turnout_boost: float = 0.0,
    ):
        self.seed = seed
        self.personas_per_district = personas_per_district
        self.llm_batch_size = llm_batch_size
        self.model = model
        self.use_batch_api = use_batch_api
        self.factor_weights = factor_weights
        self.swing_noise_offset = swing_noise_offset
        self.independent_loyalty_score = independent_loyalty_score
        self.turnout_boost = turnout_boost

        # データ読み込み
        self.archetype_config = load_archetype_config()
        self.archetypes = self.archetype_config["persona_archetypes"]
        self.districts = load_district_data()
        self.candidates_by_district = load_candidates()

        # 政党名マスタ
        parties_path = DATA_DIR / "parties.json"
        with open(parties_path, "r", encoding="utf-8") as f:
            self.parties = {p["id"]: p for p in json.load(f)}

    def run_district(self, district_row: dict) -> DistrictResult:
        """1つの選挙区のシミュレーションを実行"""

        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        district_name = district_row.get("選挙区", district_id)

        logger.info(f"シミュレーション開始: {district_name}")

        # 1. ペルソナ生成
        personas = generate_personas_for_district(
            district_row, self.archetypes,
            self.personas_per_district, self.seed
        )

        # 2. 候補者データ取得
        candidates = self.candidates_by_district.get(district_id, [])
        if not candidates:
            logger.warning(f"候補者データなし: {district_id}")
            # district_idのフォーマットが違う可能性を考慮
            alt_id = f"{int(district_row['都道府県コード'])}_{district_row['区番号']}"
            candidates = self.candidates_by_district.get(alt_id, [])

        # 3. 投票率ブースト適用
        if self.turnout_boost != 0.0:
            for p in personas:
                p.turnout_probability = max(0.05, min(0.95, p.turnout_probability + self.turnout_boost))

        # 4. ルールベース投票（全ペルソナ）
        decisions: list[VoteDecision] = []
        llm_personas: list[tuple[int, Persona]] = []

        for i, persona in enumerate(personas):
            decision = calculate_vote(
                persona, candidates, district_row,
                factor_weights=self.factor_weights,
                swing_noise_offset=self.swing_noise_offset,
                independent_loyalty_score=self.independent_loyalty_score,
            )
            decisions.append(decision)

            # LLM処理が必要なペルソナを記録
            if decision.needs_llm and decision.will_vote:
                llm_personas.append((i, persona))

        logger.info(
            f"  {district_name}: {len(personas)}名生成、"
            f"投票{sum(1 for d in decisions if d.will_vote)}名、"
            f"LLM必要{len(llm_personas)}名"
        )

        # 4. 集計
        result = aggregate_district_results(
            district_id=district_id,
            district_name=district_name,
            personas=personas,
            decisions=decisions,
            candidates=candidates,
        )

        return result

    def run_pilot(self, district_ids: list[str] | None = None) -> list[DistrictResult]:
        """パイロット実行（指定選挙区 or デフォルト10選挙区）"""

        if district_ids is None:
            # デフォルトパイロット選挙区（多様性を確保）
            district_ids = [
                "13_1",   # 東京1区（都市・野党優勢）
                "01_11",  # 北海道11区（農村・自民優勢）
                "27_1",   # 大阪1区（維新地盤）
                "47_1",   # 沖縄1区（独自政治）
                "23_1",   # 愛知1区（都市・接戦）
                "05_1",   # 秋田1区（農村・高齢化）
                "14_1",   # 神奈川1区（都市・接戦）
                "26_1",   # 京都1区（共産一定勢力）
                "40_1",   # 福岡1区（都市・保守）
                "32_1",   # 島根1区（農村・保守）
            ]

        results = []
        for district_row in self.districts:
            did = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
            if did in district_ids:
                result = self.run_district(district_row)
                results.append(result)

        return results

    def run_all(self) -> list[DistrictResult]:
        """全289選挙区のシミュレーションを実行"""
        results = []
        for i, district_row in enumerate(self.districts):
            result = self.run_district(district_row)
            results.append(result)
            if (i + 1) % 50 == 0:
                logger.info(f"進捗: {i + 1}/{len(self.districts)} 選挙区完了")
        return results

    def run_experiment(
        self,
        mode: str = "pilot",
        district_ids: list[str] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> tuple[str, list[DistrictResult]]:
        """バージョン管理付きシミュレーション実行

        Args:
            mode: "pilot" (10選挙区) or "all" (289選挙区)
            district_ids: 明示的な選挙区指定（modeより優先）
            description: 実験の説明
            tags: タグリスト

        Returns:
            (experiment_id, results) のタプル
        """
        from ..experiment_manager import ExperimentManager

        manager = ExperimentManager()
        experiment_id = manager.generate_experiment_id(self.seed)
        exp_dir = manager.create_experiment_dir(experiment_id)

        logger.info(f"実験開始: {experiment_id}")
        start_time = time.time()

        # シミュレーション実行
        if district_ids is not None:
            results = self.run_pilot(district_ids=district_ids)
        elif mode == "all":
            results = self.run_all()
        else:
            results = self.run_pilot()

        duration = time.time() - start_time

        # 結果エクスポート（既存メソッドを利用）
        self.export_results(results, exp_dir)

        # バリデーション実行・保存
        report = validate_results(results)
        manager.write_validation_report(exp_dir, report)

        # 実行した選挙区IDを記録
        run_district_ids = [r.district_id for r in results]
        total_personas = sum(r.total_personas for r in results)

        # サマリ情報を取得
        summary = self._build_summary(results)

        # メタデータ書き込み
        parameters = {
            "seed": self.seed,
            "personas_per_district": self.personas_per_district,
            "llm_batch_size": self.llm_batch_size,
            "model": self.model,
            "use_batch_api": self.use_batch_api,
            "mode": mode,
            "district_ids": run_district_ids,
            "district_count": len(results),
            "total_personas": total_personas,
            "factor_weights": self.factor_weights,
            "swing_noise_offset": self.swing_noise_offset,
            "independent_loyalty_score": self.independent_loyalty_score,
            "turnout_boost": self.turnout_boost,
        }

        results_summary = {
            "national_turnout_rate": summary["national_turnout_rate"],
            "smd_seats": summary["smd_seats"],
            "validation_passed": report.passed,
        }

        metadata = manager.write_metadata(
            experiment_dir=exp_dir,
            experiment_id=experiment_id,
            duration_seconds=duration,
            description=description,
            tags=tags or [],
            parameters=parameters,
            results_summary=results_summary,
            validation_passed=report.passed,
        )

        logger.info(
            f"実験完了: {experiment_id} "
            f"({len(results)}選挙区, {duration:.1f}秒, "
            f"バリデーション{'OK' if report.passed else 'NG'})"
        )

        return experiment_id, results

    def prepare_llm_batches(
        self,
        district_row: dict,
        personas: list[Persona],
        llm_persona_indices: list[int],
    ) -> list[dict]:
        """LLM処理用のバッチリクエストを準備"""

        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        candidates = self.candidates_by_district.get(district_id, [])

        batches = []
        for batch_start in range(0, len(llm_persona_indices), self.llm_batch_size):
            batch_indices = llm_persona_indices[batch_start:batch_start + self.llm_batch_size]
            batch_personas = [asdict(personas[i]) for i in batch_indices]

            prompt = build_batch_prompt(
                district_name=district_row.get("選挙区", district_id),
                area_description=district_row.get("対象地域", ""),
                candidates=candidates,
                district_context=district_row,
                personas=batch_personas,
            )

            batch_request = {
                "custom_id": f"{district_id}_batch_{batch_start}",
                "params": {
                    "model": self.model,
                    "max_tokens": 2000,
                    "temperature": 0.7,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
            }
            batches.append(batch_request)

        return batches

    def export_results(self, results: list[DistrictResult], output_dir: str | Path):
        """結果をCSV/JSONで出力"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 選挙区別結果CSV
        csv_path = output_dir / "district_results.csv"
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

        # 比例ブロック別結果
        proportional_path = output_dir / "proportional_results.csv"
        self._export_proportional_results(results, proportional_path)

        # 全体サマリJSON
        summary = self._build_summary(results)
        summary_path = output_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"結果出力完了: {output_dir}")

    def _export_proportional_results(self, results: list[DistrictResult], path: Path):
        """比例代表ブロック別の集計"""
        blocks_path = DATA_DIR / "proportional_blocks.json"
        with open(blocks_path, "r", encoding="utf-8") as f:
            blocks = json.load(f)

        prefs_path = DATA_DIR / "prefectures.json"
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefectures = json.load(f)

        # 都道府県コード → 比例ブロック名マッピング
        pref_to_block = {}
        for pref in prefectures:
            pref_to_block[pref["code"]] = pref.get("proportional_block", "")

        # 結果をブロックごとに集計
        block_votes: dict[str, dict[str, int]] = {}
        for r in results:
            pref_code = int(r.district_id.split("_")[0])
            block_name = pref_to_block.get(pref_code, "unknown")
            if block_name not in block_votes:
                block_votes[block_name] = {}
            for party, votes in r.proportional_votes.items():
                block_votes[block_name][party] = block_votes[block_name].get(party, 0) + votes

        # ドント式で議席配分
        block_seats_map = {b["id"]: b.get("total_seats", b.get("seats", 0)) for b in blocks}

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "block", "party", "vote_count", "vote_share", "seats_won"
            ])
            writer.writeheader()
            for block_id, votes in block_votes.items():
                total = sum(votes.values())
                seats = block_seats_map.get(block_id, 0)
                allocated = dhondt_allocation(votes, seats)
                for party, count in sorted(votes.items(), key=lambda x: -x[1]):
                    writer.writerow({
                        "block": block_id,
                        "party": party,
                        "vote_count": count,
                        "vote_share": round(count / total, 4) if total > 0 else 0,
                        "seats_won": allocated.get(party, 0),
                    })

    def _build_summary(self, results: list[DistrictResult]) -> dict:
        """全体サマリを構築（SMD + 比例代表 + 合計議席）"""
        party_seats = {}
        total_turnout = 0
        total_personas = 0

        for r in results:
            total_turnout += r.turnout_count
            total_personas += r.total_personas
            if r.winner_party:
                party_seats[r.winner_party] = party_seats.get(r.winner_party, 0) + 1

        # 比例代表議席の算出
        proportional_seats = self._calc_proportional_seats(results)

        # 合計議席（SMD + PR）
        all_parties = sorted(set(party_seats.keys()) | set(proportional_seats.keys()))
        total_seats = {}
        for party in all_parties:
            smd = party_seats.get(party, 0)
            pr = proportional_seats.get(party, 0)
            total_seats[party] = {"smd": smd, "pr": pr, "total": smd + pr}

        # 過半数判定（衆議院 465議席の過半数 = 233）
        MAJORITY = 233
        coalition_totals = {}
        for party, seats in total_seats.items():
            coalition_totals[party] = seats["total"]

        return {
            "total_districts": len(results),
            "total_personas": total_personas,
            "national_turnout_rate": round(total_turnout / total_personas, 4) if total_personas > 0 else 0,
            "smd_seats": party_seats,
            "proportional_seats": proportional_seats,
            "total_seats": total_seats,
            "majority_threshold": MAJORITY,
            "simulation_config": {
                "seed": self.seed,
                "personas_per_district": self.personas_per_district,
                "model": self.model,
                "factor_weights": self.factor_weights,
                "swing_noise_offset": self.swing_noise_offset,
                "independent_loyalty_score": self.independent_loyalty_score,
                "turnout_boost": self.turnout_boost,
            },
        }

    def _calc_proportional_seats(self, results: list[DistrictResult]) -> dict[str, int]:
        """全ブロックの比例代表議席を集計"""
        blocks_path = DATA_DIR / "proportional_blocks.json"
        prefs_path = DATA_DIR / "prefectures.json"

        try:
            with open(blocks_path, "r", encoding="utf-8") as f:
                blocks = json.load(f)
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefectures = json.load(f)
        except FileNotFoundError:
            return {}

        pref_to_block = {}
        for pref in prefectures:
            pref_to_block[pref["code"]] = pref.get("proportional_block", "")

        # ブロック別の投票集計
        block_votes: dict[str, dict[str, int]] = {}
        for r in results:
            pref_code = int(r.district_id.split("_")[0])
            block_name = pref_to_block.get(pref_code, "unknown")
            if block_name not in block_votes:
                block_votes[block_name] = {}
            for party, votes in r.proportional_votes.items():
                block_votes[block_name][party] = block_votes[block_name].get(party, 0) + votes

        block_seats_map = {b["id"]: b.get("total_seats", b.get("seats", 0)) for b in blocks}

        # ブロックごとにドント式配分し全国合計
        national_pr_seats: dict[str, int] = {}
        for block_id, votes in block_votes.items():
            seats = block_seats_map.get(block_id, 0)
            if seats > 0:
                allocated = dhondt_allocation(votes, seats)
                for party, s in allocated.items():
                    national_pr_seats[party] = national_pr_seats.get(party, 0) + s

        return national_pr_seats


def dhondt_allocation(votes: dict[str, int], total_seats: int) -> dict[str, int]:
    """ドント式による議席配分"""
    seats = {party: 0 for party in votes}
    for _ in range(total_seats):
        quotients = {party: v / (seats[party] + 1) for party, v in votes.items() if v > 0}
        if not quotients:
            break
        winner = max(quotients, key=quotients.get)
        seats[winner] += 1
    return seats
