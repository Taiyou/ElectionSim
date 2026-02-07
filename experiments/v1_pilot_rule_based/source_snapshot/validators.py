"""
シミュレーション結果のバリデーション

世論調査との整合性、投票率の妥当性、属性別傾向の確認を行う。
"""

import logging
from .result_aggregator import DistrictResult

logger = logging.getLogger(__name__)


class ValidationReport:
    def __init__(self):
        self.checks: list[dict] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def add_check(self, name: str, passed: bool, detail: str):
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.warnings.append(f"{name}: {detail}")

    def add_error(self, message: str):
        self.errors.append(message)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        lines = [f"バリデーション結果: {passed}/{total} パス"]
        if self.warnings:
            lines.append(f"  警告: {len(self.warnings)}件")
            for w in self.warnings[:10]:
                lines.append(f"    - {w}")
        if self.errors:
            lines.append(f"  エラー: {len(self.errors)}件")
            for e in self.errors:
                lines.append(f"    - {e}")
        return "\n".join(lines)


def validate_results(results: list[DistrictResult]) -> ValidationReport:
    """全選挙区の結果をバリデーション"""
    report = ValidationReport()

    if not results:
        report.add_error("結果が空です")
        return report

    # 1. 全国投票率の妥当性（40-65%が期待範囲）
    total_voted = sum(r.turnout_count for r in results)
    total_personas = sum(r.total_personas for r in results)
    national_turnout = total_voted / total_personas if total_personas > 0 else 0

    report.add_check(
        "全国投票率",
        0.35 <= national_turnout <= 0.70,
        f"{national_turnout:.1%}（期待: 35-70%）"
    )

    # 2. 各選挙区の投票率チェック
    extreme_turnout = []
    for r in results:
        if r.turnout_rate < 0.20 or r.turnout_rate > 0.85:
            extreme_turnout.append(f"{r.district_name}: {r.turnout_rate:.1%}")

    report.add_check(
        "選挙区別投票率（異常値）",
        len(extreme_turnout) == 0,
        f"{len(extreme_turnout)}選挙区で異常値: {', '.join(extreme_turnout[:5])}" if extreme_turnout else "正常"
    )

    # 3. 候補者0票チェック
    zero_vote_districts = []
    for r in results:
        if r.winner_votes == 0:
            zero_vote_districts.append(r.district_name)

    report.add_check(
        "当選者の得票",
        len(zero_vote_districts) == 0,
        f"{len(zero_vote_districts)}選挙区で当選者0票" if zero_vote_districts else "正常"
    )

    # 4. 政党別小選挙区議席数チェック
    party_seats = {}
    for r in results:
        if r.winner_party:
            party_seats[r.winner_party] = party_seats.get(r.winner_party, 0) + 1

    # 自民党が全議席、または0議席は異常
    ldp_seats = party_seats.get("ldp", 0)
    report.add_check(
        "自民党議席数",
        10 <= ldp_seats <= 250,
        f"{ldp_seats}議席（期待: 10-250）"
    )

    # 5. 比例代表の政党分布チェック
    total_proportional = {}
    for r in results:
        for party, votes in r.proportional_votes.items():
            total_proportional[party] = total_proportional.get(party, 0) + votes

    prop_total = sum(total_proportional.values())
    if prop_total > 0:
        ldp_prop_share = total_proportional.get("ldp", 0) / prop_total
        report.add_check(
            "自民党比例得票率",
            0.15 <= ldp_prop_share <= 0.50,
            f"{ldp_prop_share:.1%}（期待: 15-50%）"
        )

    # 6. アーキタイプ別投票傾向チェック
    _validate_archetype_tendencies(results, report)

    # 7. 棄権率の妥当性
    abstention_rate = 1 - national_turnout
    report.add_check(
        "棄権率",
        0.30 <= abstention_rate <= 0.65,
        f"{abstention_rate:.1%}（期待: 30-65%）"
    )

    return report


def _validate_archetype_tendencies(results: list[DistrictResult], report: ValidationReport):
    """アーキタイプ別の投票傾向が合理的かチェック"""

    # 全結果のアーキタイプ別データを集約
    arch_totals: dict[str, dict] = {}
    for r in results:
        for arch, data in r.archetype_breakdown.items():
            if arch not in arch_totals:
                arch_totals[arch] = {"count": 0, "voted": 0, "smd_parties": {}}
            arch_totals[arch]["count"] += data["count"]
            arch_totals[arch]["voted"] += data["voted"]
            for party, votes in data.get("smd_parties", {}).items():
                arch_totals[arch]["smd_parties"][party] = (
                    arch_totals[arch]["smd_parties"].get(party, 0) + votes
                )

    # rural_farmer は ldp が最多政党であるべき
    if "rural_farmer" in arch_totals:
        farmer_parties = arch_totals["rural_farmer"]["smd_parties"]
        if farmer_parties:
            top_party = max(farmer_parties, key=farmer_parties.get)
            report.add_check(
                "農村農業従事者のLDP傾向",
                top_party == "ldp",
                f"最多投票先: {top_party}（期待: ldp）"
            )

    # labor_union_member は chudo (旧cdp系) が上位であるべき
    if "labor_union_member" in arch_totals:
        union_parties = arch_totals["labor_union_member"]["smd_parties"]
        if union_parties:
            ldp_share = union_parties.get("ldp", 0) / sum(union_parties.values()) if sum(union_parties.values()) > 0 else 0
            report.add_check(
                "労働組合員のLDP非偏重",
                ldp_share < 0.50,
                f"LDP得票率: {ldp_share:.1%}（期待: <50%）"
            )

    # 投票率チェック: 高齢者 > 若年層
    elderly_archetypes = ["active_elderly", "late_elderly"]
    young_archetypes = ["urban_young_worker", "university_student"]

    elderly_rate = _calc_archetype_turnout(arch_totals, elderly_archetypes)
    young_rate = _calc_archetype_turnout(arch_totals, young_archetypes)

    if elderly_rate is not None and young_rate is not None:
        report.add_check(
            "高齢者投票率 > 若年層投票率",
            elderly_rate > young_rate,
            f"高齢者: {elderly_rate:.1%}, 若年層: {young_rate:.1%}"
        )


def _calc_archetype_turnout(totals: dict, archetypes: list[str]) -> float | None:
    """指定アーキタイプの平均投票率を算出"""
    count = 0
    voted = 0
    for arch in archetypes:
        if arch in totals:
            count += totals[arch]["count"]
            voted += totals[arch]["voted"]
    return voted / count if count > 0 else None
