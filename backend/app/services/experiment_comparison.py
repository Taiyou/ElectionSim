"""
実験比較サービス

2つの実験間、または実験と実選挙結果の比較を行う。

比較指標:
- 当選者一致率: 予測 winner_party と比較対象の一致率
- 議席数MAE: 政党別 abs(予測席数 - 比較席数) の平均
- 投票率相関: 予測投票率と比較投票率のPearson相関
- 接戦区精度: margin下位25%選挙区での当選者一致率
- 政権予測正否: 過半数連合の正誤
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from .experiment_manager import ExperimentManager

logger = logging.getLogger(__name__)

MAJORITY_THRESHOLD = 233  # 衆議院過半数


@dataclass
class DistrictComparison:
    district_id: str
    district_name: str
    party_a: str
    party_b: str
    match: bool


@dataclass
class ComparisonReport:
    experiment_a: str
    experiment_b: str  # 実選挙結果の場合は "actual"
    common_districts: int
    winner_match_rate: float
    district_comparisons: list[DistrictComparison] = field(default_factory=list)
    seat_diff: dict[str, dict] = field(default_factory=dict)  # party -> {a, b, diff}
    seat_mae: float = 0.0
    turnout_correlation: float | None = None
    battleground_accuracy: float | None = None  # 接戦区精度


def _pearson_r(xs: list[float], ys: list[float]) -> float | None:
    """Pearson相関係数を計算"""
    n = len(xs)
    if n < 3:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return None
    return cov / denom


def _build_district_map(district_results: list[dict]) -> dict[str, dict]:
    """district_id をキーとした辞書を作成"""
    return {r["district_id"]: r for r in district_results}


def _count_seats(district_results: list[dict]) -> dict[str, int]:
    """政党別の小選挙区議席数を集計"""
    seats: dict[str, int] = {}
    for r in district_results:
        party = r.get("winner_party", "")
        if party:
            seats[party] = seats.get(party, 0) + 1
    return seats


def compare_results(
    results_a: list[dict],
    results_b: list[dict],
    label_a: str,
    label_b: str,
) -> ComparisonReport:
    """2つの選挙区結果リストを比較"""
    map_a = _build_district_map(results_a)
    map_b = _build_district_map(results_b)

    # 共通選挙区のみ比較
    common_ids = sorted(set(map_a.keys()) & set(map_b.keys()))

    if not common_ids:
        return ComparisonReport(
            experiment_a=label_a,
            experiment_b=label_b,
            common_districts=0,
            winner_match_rate=0.0,
        )

    # 選挙区別比較
    comparisons = []
    matches = 0
    turnouts_a = []
    turnouts_b = []

    for did in common_ids:
        ra = map_a[did]
        rb = map_b[did]
        party_a = ra.get("winner_party", "")
        party_b = rb.get("winner_party", "")
        match = party_a == party_b
        if match:
            matches += 1

        comparisons.append(DistrictComparison(
            district_id=did,
            district_name=ra.get("district_name", did),
            party_a=party_a,
            party_b=party_b,
            match=match,
        ))

        # 投票率
        tr_a = ra.get("turnout_rate")
        tr_b = rb.get("turnout_rate")
        if tr_a is not None and tr_b is not None:
            turnouts_a.append(float(tr_a))
            turnouts_b.append(float(tr_b))

    winner_match_rate = matches / len(common_ids) if common_ids else 0.0

    # 議席数比較
    seats_a = _count_seats([map_a[did] for did in common_ids])
    seats_b = _count_seats([map_b[did] for did in common_ids])
    all_parties = sorted(set(seats_a.keys()) | set(seats_b.keys()))

    seat_diff = {}
    total_abs_error = 0
    for party in all_parties:
        sa = seats_a.get(party, 0)
        sb = seats_b.get(party, 0)
        diff = sa - sb
        seat_diff[party] = {"a": sa, "b": sb, "diff": diff}
        total_abs_error += abs(diff)

    seat_mae = total_abs_error / len(all_parties) if all_parties else 0.0

    # 投票率相関
    turnout_corr = _pearson_r(turnouts_a, turnouts_b)

    # 接戦区精度（margin下位25%）
    battleground_accuracy = _calc_battleground_accuracy(comparisons, map_a)

    return ComparisonReport(
        experiment_a=label_a,
        experiment_b=label_b,
        common_districts=len(common_ids),
        winner_match_rate=round(winner_match_rate, 4),
        district_comparisons=comparisons,
        seat_diff=seat_diff,
        seat_mae=round(seat_mae, 2),
        turnout_correlation=round(turnout_corr, 4) if turnout_corr is not None else None,
        battleground_accuracy=round(battleground_accuracy, 4) if battleground_accuracy is not None else None,
    )


def _calc_battleground_accuracy(
    comparisons: list[DistrictComparison],
    results_map: dict[str, dict],
) -> float | None:
    """接戦区（margin下位25%）での当選者一致率"""
    # margin でソートし下位25%を接戦区とする
    margins = []
    for comp in comparisons:
        r = results_map.get(comp.district_id, {})
        margin = r.get("margin")
        if margin is not None:
            margins.append((int(margin), comp))

    if len(margins) < 4:
        return None

    margins.sort(key=lambda x: x[0])
    cutoff = max(1, len(margins) // 4)
    battleground = margins[:cutoff]

    matches = sum(1 for _, comp in battleground if comp.match)
    return matches / len(battleground)


def compare_experiments(exp_id_a: str, exp_id_b: str) -> ComparisonReport:
    """2つの実験を比較"""
    manager = ExperimentManager()
    data_a = manager.load_experiment(exp_id_a)
    data_b = manager.load_experiment(exp_id_b)

    return compare_results(
        results_a=data_a["district_results"],
        results_b=data_b["district_results"],
        label_a=exp_id_a,
        label_b=exp_id_b,
    )


def compare_with_actual(exp_id: str) -> ComparisonReport:
    """実験結果と実選挙結果を比較"""
    manager = ExperimentManager()
    data_exp = manager.load_experiment(exp_id)
    actual = manager.load_actual_results()

    if actual is None or "district_results" not in actual:
        raise FileNotFoundError(
            "実選挙結果が見つかりません。"
            "scripts/load_actual_results.py で投入してください。"
        )

    return compare_results(
        results_a=data_exp["district_results"],
        results_b=actual["district_results"],
        label_a=exp_id,
        label_b="actual",
    )


def format_comparison_report(report: ComparisonReport) -> str:
    """比較レポートをテキストフォーマット"""
    lines = []
    lines.append("=" * 60)
    lines.append("実験比較レポート")
    lines.append("=" * 60)
    lines.append(f"  実験A: {report.experiment_a}")
    lines.append(f"  実験B: {report.experiment_b}")
    lines.append(f"  共通選挙区数: {report.common_districts}")
    lines.append("")

    # 主要指標
    lines.append("--- 主要指標 ---")
    lines.append(f"  当選政党一致率: {report.winner_match_rate:.1%}")
    lines.append(f"  議席数MAE: {report.seat_mae:.1f}")
    if report.turnout_correlation is not None:
        lines.append(f"  投票率相関: {report.turnout_correlation:.3f}")
    if report.battleground_accuracy is not None:
        lines.append(f"  接戦区精度: {report.battleground_accuracy:.1%}")
    lines.append("")

    # 議席数差分
    if report.seat_diff:
        lines.append("--- 政党別議席数 ---")
        lines.append(f"  {'政党':10s} {'A':>5s} {'B':>5s} {'差分':>5s}")
        for party, d in sorted(report.seat_diff.items(), key=lambda x: -abs(x[1]["diff"])):
            lines.append(f"  {party:10s} {d['a']:5d} {d['b']:5d} {d['diff']:+5d}")
        lines.append("")

    # 不一致選挙区
    mismatches = [c for c in report.district_comparisons if not c.match]
    if mismatches:
        lines.append(f"--- 不一致選挙区 ({len(mismatches)}件) ---")
        for c in mismatches:
            lines.append(f"  {c.district_name}: {c.party_a} (A) vs {c.party_b} (B)")
    else:
        lines.append("--- 全選挙区で当選政党が一致 ---")

    lines.append("=" * 60)
    return "\n".join(lines)
