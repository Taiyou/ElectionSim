"""
シミュレーション実験 vs 実選挙結果 比較スクリプト

2026年2月8日 第51回衆議院議員総選挙の実際の結果と、
各シミュレーション実験の予測結果を比較する。

使い方:
  python scripts/compare_with_actual.py
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results" / "experiments"
REPORT_DIR = BASE_DIR / "experiments"
ACTUAL_CSV = RESULTS_DIR / "actual" / "district_results.csv"

# ============================================================
# 実際の選挙結果（2026-02-08 第51回衆院選）
# 出典: NHK, 日経新聞, 時事通信, zeimo.jp
# ============================================================

ACTUAL_TURNOUT = 0.5568

ACTUAL_SMD_SEATS = {
    "ldp": 249,
    "chudo": 7,
    "ishin": 20,
    "dpfp": 8,
    "sansei": 0,
    "mirai": 0,
    "jcp": 0,
    "reiwa": 0,
    "genzei": 1,
    "independent": 4,
    "hoshuto": 0,
    "shamin": 0,
    "other": 0,
}

ACTUAL_PR_SEATS = {
    "ldp": 67,
    "chudo": 42,
    "dpfp": 20,
    "ishin": 16,
    "sansei": 15,
    "mirai": 11,
    "jcp": 4,
    "reiwa": 1,
    "hoshuto": 0,
    "genzei": 0,
    "shamin": 0,
}

ACTUAL_TOTAL_SEATS = {
    p: ACTUAL_SMD_SEATS.get(p, 0) + ACTUAL_PR_SEATS.get(p, 0)
    for p in set(list(ACTUAL_SMD_SEATS.keys()) + list(ACTUAL_PR_SEATS.keys()))
}

ACTUAL_PR_VOTE_SHARE = {
    "ldp": 0.3672,
    "chudo": 0.1823,
    "dpfp": 0.0973,
    "ishin": 0.0863,
    "sansei": 0.0744,
    "mirai": 0.0666,
    "jcp": 0.0440,
    "reiwa": 0.0292,
    "hoshuto": 0.0254,
    "genzei": 0.0142,
    "shamin": 0.0127,
}

MAJORITY_THRESHOLD = 233  # 衆議院過半数

# ============================================================
# 比較対象の実験
# ============================================================

EXPERIMENTS = [
    {
        "id": "v2",
        "label": "v2 ルールベース",
        "method": "ルールベース (6要因加重)",
        "path": "sim_20260208_030926_seed42",
    },
    {
        "id": "v4b",
        "label": "v4b LLM全ペルソナ",
        "method": "LLM全ペルソナ (20人/区)",
        "path": "v4_20260209_022234_seed42",
    },
    {
        "id": "v8a",
        "label": "v8a キャリブレーションLLM",
        "method": "デカップリング + 事後キャリブレーション",
        "path": "v8a_20260209_023203_seed42",
    },
    {
        "id": "v9a",
        "label": "v9a ハイブリッド",
        "method": "ルール(安定区) + LLM(接戦区)",
        "path": "v9a_20260208_185241_seed42",
    },
    {
        "id": "v10a",
        "label": "v10a 人口統計LLM",
        "method": "census-based ペルソナ + LLM",
        "path": "v10a_merged_289_20260208_230409_seed42",
    },
    {
        "id": "v10b",
        "label": "v10b メモリ付きLLM",
        "method": "人口統計 + 記憶レイヤー + LLM",
        "path": "v10b_merged_289_20260208_193403_seed42",
    },
]

# 主要政党（表示順）
MAIN_PARTIES = ["ldp", "chudo", "ishin", "dpfp", "jcp", "sansei", "genzei", "independent", "other"]
PARTY_NAMES_JA = {
    "ldp": "自民党",
    "chudo": "中道改革連合",
    "ishin": "維新の会",
    "dpfp": "国民民主党",
    "jcp": "共産党",
    "sansei": "参政党",
    "genzei": "減税ゆうこく",
    "independent": "無所属",
    "other": "その他",
    "reiwa": "れいわ",
    "mirai": "チームみらい",
    "hoshuto": "日本保守党",
    "shamin": "社民党",
    "komei": "公明党",
}


def load_actual_districts() -> dict[str, str]:
    """実際の選挙結果CSVを読み込み、district_id -> winner_party のマップを返す"""
    if not ACTUAL_CSV.exists():
        print(f"  [WARN] 実選挙結果CSV {ACTUAL_CSV} が見つかりません", file=sys.stderr)
        return {}
    result = {}
    with open(ACTUAL_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["district_id"]] = row["winner_party"]
    return result


def load_experiment_districts(exp_path: str) -> list[dict]:
    """実験のdistrict_results.csvを読み込む"""
    path = RESULTS_DIR / exp_path / "district_results.csv"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_summary(exp_path: str) -> dict | None:
    path = RESULTS_DIR / exp_path / "summary.json"
    if not path.exists():
        print(f"  [WARN] {path} が見つかりません", file=sys.stderr)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_districts(exp_districts: list[dict], actual_map: dict[str, str]) -> dict:
    """選挙区レベルで予測と実際を比較"""
    matches = 0
    mismatches = []
    common = 0

    for row in exp_districts:
        did = row["district_id"]
        if did not in actual_map:
            continue
        common += 1
        pred_party = row["winner_party"]
        actual_party = actual_map[did]
        if pred_party == actual_party:
            matches += 1
        else:
            mismatches.append({
                "district_id": did,
                "district_name": row.get("district_name", did),
                "predicted": pred_party,
                "actual": actual_party,
                "margin": int(row.get("margin", 0)),
            })

    match_rate = matches / common if common > 0 else 0

    # 地域別の一致率
    region_stats = defaultdict(lambda: {"total": 0, "match": 0})
    REGION_MAP = {
        "01": "北海道", "02": "東北", "03": "東北", "04": "東北",
        "05": "東北", "06": "東北", "07": "東北",
        "08": "北関東", "09": "北関東", "10": "北関東",
        "11": "南関東", "12": "南関東", "13": "東京", "14": "南関東",
        "15": "北陸信越", "16": "北陸信越", "17": "北陸信越",
        "18": "北陸信越", "19": "北陸信越", "20": "北陸信越",
        "21": "東海", "22": "東海", "23": "東海", "24": "東海",
        "25": "近畿", "26": "近畿", "27": "近畿", "28": "近畿",
        "29": "近畿", "30": "近畿",
        "31": "中国", "32": "中国", "33": "中国", "34": "中国", "35": "中国",
        "36": "四国", "37": "四国", "38": "四国", "39": "四国",
        "40": "九州", "41": "九州", "42": "九州", "43": "九州",
        "44": "九州", "45": "九州", "46": "九州", "47": "沖縄",
    }
    for row in exp_districts:
        did = row["district_id"]
        if did not in actual_map:
            continue
        pref_code = did.split("_")[0]
        region = REGION_MAP.get(pref_code, "不明")
        region_stats[region]["total"] += 1
        if row["winner_party"] == actual_map[did]:
            region_stats[region]["match"] += 1

    # 不一致パターン分析
    mismatch_patterns = Counter()
    for m in mismatches:
        pattern = f"{m['predicted']}→{m['actual']}"
        mismatch_patterns[pattern] += 1

    return {
        "common": common,
        "matches": matches,
        "match_rate": match_rate,
        "mismatches": mismatches,
        "region_stats": dict(region_stats),
        "mismatch_patterns": mismatch_patterns,
    }


def load_persona_decisions(exp_path: str) -> dict[str, list[dict]] | None:
    """実験のpersona_decisions.jsonを読み込む"""
    path = RESULTS_DIR / exp_path / "persona_decisions.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calc_party_accuracy(
    exp_districts: list[dict], actual_map: dict[str, str]
) -> dict[str, dict]:
    """政党別の的中率を計算

    Returns:
        {party: {"predicted": N, "correct": N, "accuracy": float}}
    """
    stats: dict[str, dict] = {}
    for row in exp_districts:
        did = row["district_id"]
        if did not in actual_map:
            continue
        pred = row["winner_party"]
        actual = actual_map[did]
        if pred not in stats:
            stats[pred] = {"predicted": 0, "correct": 0}
        stats[pred]["predicted"] += 1
        if pred == actual:
            stats[pred]["correct"] += 1

    for party, s in stats.items():
        s["accuracy"] = s["correct"] / s["predicted"] if s["predicted"] > 0 else 0.0
    return stats


def calc_confidence_accuracy(
    persona_decisions: dict[str, list[dict]],
    exp_districts: list[dict],
    actual_map: dict[str, str],
) -> dict[str, dict]:
    """確信度別の的中率を計算

    ペルソナの確信度を選挙区ごとに平均し、確信度ビンごとの選挙区的中率を計算する。

    Returns:
        {bin_label: {"total": N, "correct": N, "accuracy": float, "districts": [...]}}
    """
    # 選挙区ごとの平均確信度を計算（投票したペルソナのみ）
    district_confidence: dict[str, float] = {}
    for did, personas in persona_decisions.items():
        voters = [p for p in personas if p.get("will_vote") and p.get("confidence") is not None]
        if voters:
            avg_conf = sum(p["confidence"] for p in voters) / len(voters)
            district_confidence[did] = avg_conf

    # 選挙区ごとの的中・外れを判定
    district_winner_map = {}
    for row in exp_districts:
        district_winner_map[row["district_id"]] = row["winner_party"]

    # ビンの定義
    bins = [
        ("低 (< 0.55)", 0.0, 0.55),
        ("中低 (0.55-0.65)", 0.55, 0.65),
        ("中 (0.65-0.75)", 0.65, 0.75),
        ("中高 (0.75-0.85)", 0.75, 0.85),
        ("高 (>= 0.85)", 0.85, 1.01),
    ]

    results = {}
    for label, lo, hi in bins:
        districts_in_bin = []
        correct = 0
        for did, conf in district_confidence.items():
            if lo <= conf < hi and did in actual_map and did in district_winner_map:
                pred = district_winner_map[did]
                actual = actual_map[did]
                hit = pred == actual
                if hit:
                    correct += 1
                districts_in_bin.append({
                    "district_id": did,
                    "confidence": round(conf, 3),
                    "predicted": pred,
                    "actual": actual,
                    "hit": hit,
                })
        total = len(districts_in_bin)
        results[label] = {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0.0,
            "districts": districts_in_bin,
        }

    return results


def build_full_district_list(
    exp_districts: list[dict], actual_map: dict[str, str]
) -> list[dict]:
    """全289選挙区の的中/外れ一覧を作成"""
    rows = []
    for row in exp_districts:
        did = row["district_id"]
        if did not in actual_map:
            continue
        pred = row["winner_party"]
        actual = actual_map[did]
        hit = pred == actual
        rows.append({
            "district_id": did,
            "district_name": row.get("district_name", did),
            "predicted": pred,
            "actual": actual,
            "hit": hit,
            "margin": int(row.get("margin", 0)),
        })
    return rows


def calc_llm_only_accuracy(
    persona_decisions: dict[str, list[dict]],
    actual_map: dict[str, str],
) -> dict:
    """LLM投票者のみの投票結果から選挙区勝者を再集計し、実際と比較する。

    v8a以降のデカップリング方式では投票参加はルールベース、投票先はLLMが決定。
    この関数はLLMが決めた投票先のみから選挙区勝者を算出し、的中率を計算する。

    Returns:
        {
            "total": 共通選挙区数,
            "correct": 的中数,
            "accuracy": 的中率,
            "party_accuracy": {party: {predicted, correct, accuracy}},
            "districts": [{district_id, district_name, llm_winner, actual, hit, votes}],
        }
    """
    districts = []
    party_stats: dict[str, dict] = {}

    for did, personas in persona_decisions.items():
        if did not in actual_map:
            continue

        # 投票者のsmd_party別の得票を集計
        vote_counts: dict[str, int] = {}
        for p in personas:
            if p.get("will_vote") and p.get("smd_party"):
                party = p["smd_party"]
                vote_counts[party] = vote_counts.get(party, 0) + 1

        if not vote_counts:
            continue

        # 最多得票の政党を勝者とする（同票の場合はソートで安定化）
        llm_winner = max(sorted(vote_counts.keys()), key=lambda k: vote_counts[k])
        actual = actual_map[did]
        hit = llm_winner == actual

        # 政党別集計
        if llm_winner not in party_stats:
            party_stats[llm_winner] = {"predicted": 0, "correct": 0}
        party_stats[llm_winner]["predicted"] += 1
        if hit:
            party_stats[llm_winner]["correct"] += 1

        districts.append({
            "district_id": did,
            "llm_winner": llm_winner,
            "actual": actual,
            "hit": hit,
            "votes": vote_counts,
            "total_voters": sum(vote_counts.values()),
        })

    total = len(districts)
    correct = sum(1 for d in districts if d["hit"])

    for party, s in party_stats.items():
        s["accuracy"] = s["correct"] / s["predicted"] if s["predicted"] > 0 else 0.0

    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0.0,
        "party_accuracy": party_stats,
        "districts": districts,
    }


def _pearson_r(xs: list[float], ys: list[float]) -> float | None:
    """Pearson相関係数"""
    n = len(xs)
    if n < 3:
        return None
    import math
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return None
    return cov / denom


def calc_battleground_accuracy(
    exp_districts: list[dict], actual_map: dict[str, str]
) -> dict | None:
    """接戦区精度：予測margin下位25%の選挙区での的中率"""
    district_data = []
    for row in exp_districts:
        did = row["district_id"]
        if did not in actual_map:
            continue
        margin = int(row.get("margin", 0))
        pred = row["winner_party"]
        actual = actual_map[did]
        district_data.append({
            "district_id": did,
            "district_name": row.get("district_name", did),
            "margin": margin,
            "predicted": pred,
            "actual": actual,
            "hit": pred == actual,
        })

    if len(district_data) < 4:
        return None

    district_data.sort(key=lambda x: x["margin"])
    cutoff = max(1, len(district_data) // 4)
    battleground = district_data[:cutoff]
    safe = district_data[cutoff:]

    bg_correct = sum(1 for d in battleground if d["hit"])
    safe_correct = sum(1 for d in safe if d["hit"])

    return {
        "battleground_count": len(battleground),
        "battleground_correct": bg_correct,
        "battleground_accuracy": bg_correct / len(battleground),
        "safe_count": len(safe),
        "safe_correct": safe_correct,
        "safe_accuracy": safe_correct / len(safe) if safe else 0,
        "battleground_districts": battleground,
    }


def load_proportional_results(exp_path: str) -> dict[str, int]:
    """比例代表の政党別議席数を読み込む"""
    path = RESULTS_DIR / exp_path / "proportional_results.csv"
    if not path.exists():
        return {}
    seats: dict[str, int] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            party = row["party"]
            sw = int(row.get("seats_won", 0))
            seats[party] = seats.get(party, 0) + sw
    return seats


def calc_swing_analysis(
    persona_decisions: dict[str, list[dict]],
    actual_map: dict[str, str],
) -> dict:
    """スイング層分析：swing_level別の投票先と的中率"""
    swing_levels = ["low", "moderate", "moderate_high", "high", "very_high"]
    level_stats: dict[str, dict] = {}

    for level in swing_levels:
        level_stats[level] = {"total_voters": 0, "party_votes": {}}

    for did, personas in persona_decisions.items():
        if did not in actual_map:
            continue
        for p in personas:
            if not p.get("will_vote") or not p.get("smd_party"):
                continue
            level = p.get("swing_level", "moderate")
            if level not in level_stats:
                level_stats[level] = {"total_voters": 0, "party_votes": {}}
            level_stats[level]["total_voters"] += 1
            party = p["smd_party"]
            level_stats[level]["party_votes"][party] = \
                level_stats[level]["party_votes"].get(party, 0) + 1

    return level_stats


def calc_abstention_analysis(
    persona_decisions: dict[str, list[dict]],
) -> dict:
    """棄権パターン分析：棄権理由の頻度分布"""
    reason_counts: dict[str, int] = {}
    total_abstained = 0
    total_personas = 0

    for did, personas in persona_decisions.items():
        for p in personas:
            total_personas += 1
            if not p.get("will_vote"):
                total_abstained += 1
                reason = p.get("abstention_reason", "不明")
                if reason:
                    # 複数理由をカンマ・読点で分割
                    for r in reason.replace("、", ",").replace("，", ",").split(","):
                        r = r.strip()
                        if r:
                            reason_counts[r] = reason_counts.get(r, 0) + 1

    return {
        "total_personas": total_personas,
        "total_abstained": total_abstained,
        "abstention_rate": total_abstained / total_personas if total_personas else 0,
        "reason_counts": reason_counts,
    }


def calc_smd_mae(predicted: dict[str, int], actual: dict[str, int]) -> float:
    all_parties = sorted(set(list(predicted.keys()) + list(actual.keys())))
    total_error = sum(abs(predicted.get(p, 0) - actual.get(p, 0)) for p in all_parties)
    return total_error / len(all_parties) if all_parties else 0.0


def calc_total_abs_error(predicted: dict[str, int], actual: dict[str, int]) -> int:
    all_parties = sorted(set(list(predicted.keys()) + list(actual.keys())))
    return sum(abs(predicted.get(p, 0) - actual.get(p, 0)) for p in all_parties)


def check_majority(smd_seats: dict[str, int]) -> bool:
    return smd_seats.get("ldp", 0) >= MAJORITY_THRESHOLD


def main():
    # 実選挙結果の選挙区データ読み込み
    actual_map = load_actual_districts()
    has_district_data = len(actual_map) > 0
    if has_district_data:
        print(f"[INFO] 実選挙結果: {len(actual_map)}選挙区の選挙区別データを読み込みました")
    else:
        print("[WARN] 選挙区別の実選挙結果データがありません。集計レベルの比較のみ行います。")

    results = []

    for exp in EXPERIMENTS:
        summary = load_summary(exp["path"])
        if summary is None:
            continue

        smd = summary.get("smd_seats", {})
        turnout = summary.get("national_turnout_rate", 0)
        total_districts = summary.get("total_districts", 0)

        ldp_diff = smd.get("ldp", 0) - ACTUAL_SMD_SEATS["ldp"]
        turnout_diff = turnout - ACTUAL_TURNOUT
        mae = calc_smd_mae(smd, ACTUAL_SMD_SEATS)
        total_abs = calc_total_abs_error(smd, ACTUAL_SMD_SEATS)
        majority_correct = check_majority(smd) == check_majority(ACTUAL_SMD_SEATS)

        # 選挙区レベル比較
        district_comp = None
        party_accuracy = None
        confidence_accuracy = None
        full_district_list = None
        battleground = None
        llm_only = None
        swing_analysis = None
        abstention_analysis = None
        pr_seats = {}
        exp_districts = []
        if has_district_data:
            exp_districts = load_experiment_districts(exp["path"])
            if exp_districts:
                district_comp = compare_districts(exp_districts, actual_map)
                party_accuracy = calc_party_accuracy(exp_districts, actual_map)
                full_district_list = build_full_district_list(exp_districts, actual_map)

                # 接戦区精度
                battleground = calc_battleground_accuracy(exp_districts, actual_map)

                # 確信度分析・LLM投票者のみ分析（persona_decisions.jsonがある場合のみ）
                persona_data = load_persona_decisions(exp["path"])
                if persona_data:
                    confidence_accuracy = calc_confidence_accuracy(
                        persona_data, exp_districts, actual_map
                    )
                    llm_only = calc_llm_only_accuracy(persona_data, actual_map)
                    swing_analysis = calc_swing_analysis(persona_data, actual_map)
                    abstention_analysis = calc_abstention_analysis(persona_data)
                else:
                    pass  # defaults already set above

        # 比例代表結果
        pr_seats = load_proportional_results(exp["path"])

        results.append({
            "exp": exp,
            "smd": smd,
            "turnout": turnout,
            "total_districts": total_districts,
            "ldp_diff": ldp_diff,
            "turnout_diff": turnout_diff,
            "mae": mae,
            "total_abs": total_abs,
            "majority_correct": majority_correct,
            "district_comp": district_comp,
            "party_accuracy": party_accuracy,
            "confidence_accuracy": confidence_accuracy,
            "full_district_list": full_district_list,
            "llm_only": llm_only,
            "battleground": battleground,
            "pr_seats": pr_seats,
            "swing_analysis": swing_analysis,
            "abstention_analysis": abstention_analysis,
        })

    # ============================================================
    # ターミナル出力
    # ============================================================

    print("=" * 80)
    print("  第51回衆議院議員総選挙（2026/2/8）シミュレーション vs 実際の結果")
    print("=" * 80)
    print()

    # --- 実際の結果 ---
    print("■ 実際の選挙結果")
    print(f"  投票率: {ACTUAL_TURNOUT:.2%}")
    print(f"  小選挙区: 自民{ACTUAL_SMD_SEATS['ldp']}, 中道{ACTUAL_SMD_SEATS['chudo']}, "
          f"維新{ACTUAL_SMD_SEATS['ishin']}, 国民{ACTUAL_SMD_SEATS['dpfp']}, "
          f"減税{ACTUAL_SMD_SEATS['genzei']}, 無所属{ACTUAL_SMD_SEATS['independent']}")
    print(f"  比例代表: 自民{ACTUAL_PR_SEATS['ldp']}, 中道{ACTUAL_PR_SEATS['chudo']}, "
          f"国民{ACTUAL_PR_SEATS['dpfp']}, 維新{ACTUAL_PR_SEATS['ishin']}, "
          f"参政{ACTUAL_PR_SEATS['sansei']}, みらい{ACTUAL_PR_SEATS['mirai']}, "
          f"共産{ACTUAL_PR_SEATS['jcp']}, れいわ{ACTUAL_PR_SEATS['reiwa']}")
    total = sum(ACTUAL_TOTAL_SEATS.values())
    print(f"  合計: 自民{ACTUAL_TOTAL_SEATS['ldp']}/{total}議席 "
          f"(単独{ACTUAL_TOTAL_SEATS['ldp']/465*100:.1f}%, 2/3={310}以上を超過)")
    print()

    # --- 小選挙区 政党別比較表 ---
    print("■ 小選挙区 政党別議席数比較")
    print()

    header = f"{'実験':22s} {'投票率':>7s} {'自民':>5s} {'中道':>5s} {'維新':>5s} {'国民':>5s} {'共産':>5s} {'他':>5s}"
    print(header)
    print("-" * len(header.encode("utf-8")))

    # 実際の結果行
    others_actual = sum(v for k, v in ACTUAL_SMD_SEATS.items()
                        if k not in ("ldp", "chudo", "ishin", "dpfp", "jcp"))
    print(f"{'★ 実際の結果':22s} {ACTUAL_TURNOUT:>6.1%} {ACTUAL_SMD_SEATS['ldp']:>5d} "
          f"{ACTUAL_SMD_SEATS['chudo']:>5d} {ACTUAL_SMD_SEATS['ishin']:>5d} "
          f"{ACTUAL_SMD_SEATS['dpfp']:>5d} {ACTUAL_SMD_SEATS['jcp']:>5d} {others_actual:>5d}")
    print("-" * len(header.encode("utf-8")))

    for r in results:
        smd = r["smd"]
        others = sum(v for k, v in smd.items()
                     if k not in ("ldp", "chudo", "ishin", "dpfp", "jcp"))
        print(f"{r['exp']['label']:22s} {r['turnout']:>6.1%} {smd.get('ldp', 0):>5d} "
              f"{smd.get('chudo', 0):>5d} {smd.get('ishin', 0):>5d} "
              f"{smd.get('dpfp', 0):>5d} {smd.get('jcp', 0):>5d} {others:>5d}")

    print()

    # --- 差分表 ---
    print("■ 小選挙区 議席数差分（実験 - 実際）")
    print()

    header2 = f"{'実験':22s} {'自民':>6s} {'中道':>6s} {'維新':>6s} {'国民':>6s} {'共産':>6s} {'合計誤差':>8s}"
    print(header2)
    print("-" * 80)

    for r in results:
        smd = r["smd"]
        diffs = {
            "ldp": smd.get("ldp", 0) - ACTUAL_SMD_SEATS["ldp"],
            "chudo": smd.get("chudo", 0) - ACTUAL_SMD_SEATS["chudo"],
            "ishin": smd.get("ishin", 0) - ACTUAL_SMD_SEATS["ishin"],
            "dpfp": smd.get("dpfp", 0) - ACTUAL_SMD_SEATS["dpfp"],
            "jcp": smd.get("jcp", 0) - ACTUAL_SMD_SEATS["jcp"],
        }
        print(f"{r['exp']['label']:22s} {diffs['ldp']:>+6d} {diffs['chudo']:>+6d} "
              f"{diffs['ishin']:>+6d} {diffs['dpfp']:>+6d} {diffs['jcp']:>+6d} "
              f"{r['total_abs']:>8d}")

    print()

    # --- 精度ランキング ---
    print("■ 精度ランキング（議席総絶対誤差の小さい順）")
    print()

    ranked = sorted(results, key=lambda r: r["total_abs"])
    for i, r in enumerate(ranked, 1):
        majority_mark = "O" if r["majority_correct"] else "X"
        dc = r["district_comp"]
        match_str = f"{dc['match_rate']:.1%}" if dc else "N/A"
        bg = r.get("battleground")
        bg_str = f"{bg['battleground_accuracy']:.0%}" if bg else "N/A"
        print(f"  {i}. {r['exp']['label']:22s}  "
              f"総誤差={r['total_abs']:>3d}席  "
              f"MAE={r['mae']:.1f}  "
              f"LDP差={r['ldp_diff']:>+4d}  "
              f"投票率差={r['turnout_diff']:>+.2%}  "
              f"区一致率={match_str:>6s}  "
              f"接戦区={bg_str:>4s}  "
              f"過半数={majority_mark}")

    print()

    # --- 選挙区レベル比較 ---
    if has_district_data:
        print("■ 選挙区レベルの当選政党一致率")
        print()

        header3 = f"{'実験':22s} {'共通区':>5s} {'一致':>5s} {'不一致':>5s} {'一致率':>7s}"
        print(header3)
        print("-" * 60)

        for r in results:
            dc = r["district_comp"]
            if dc is None:
                continue
            print(f"{r['exp']['label']:22s} {dc['common']:>5d} {dc['matches']:>5d} "
                  f"{dc['common'] - dc['matches']:>5d} {dc['match_rate']:>6.1%}")

        print()

        # 地域別一致率（最良の実験を使用）
        best_district = max(
            (r for r in results if r["district_comp"] is not None),
            key=lambda r: r["district_comp"]["match_rate"],
        )
        print(f"■ 地域別一致率（全実験比較）")
        print()

        # 地域の表示順
        REGION_ORDER = ["北海道", "東北", "北関東", "南関東", "東京", "北陸信越",
                        "東海", "近畿", "中国", "四国", "九州", "沖縄"]

        region_header = f"{'地域':10s}"
        for r in results:
            if r["district_comp"] is not None:
                region_header += f" {r['exp']['id']:>6s}"
        print(region_header)
        print("-" * (10 + 7 * sum(1 for r in results if r["district_comp"] is not None)))

        for region in REGION_ORDER:
            line = f"{region:10s}"
            for r in results:
                dc = r["district_comp"]
                if dc is None:
                    continue
                rs = dc["region_stats"].get(region)
                if rs and rs["total"] > 0:
                    rate = rs["match"] / rs["total"]
                    line += f" {rate:>5.0%} "
                else:
                    line += f"   {'--':>4s}"
            print(line)

        print()

        # 不一致パターン分析
        print("■ 不一致パターン分析（予測→実際、全実験合計）")
        print()

        all_patterns = Counter()
        for r in results:
            dc = r["district_comp"]
            if dc is None:
                continue
            all_patterns += dc["mismatch_patterns"]

        for pattern, count in all_patterns.most_common(10):
            pred, actual = pattern.split("→")
            pred_ja = PARTY_NAMES_JA.get(pred, pred)
            actual_ja = PARTY_NAMES_JA.get(actual, actual)
            print(f"  {pred_ja} → {actual_ja}: {count}件")

        print()

        # 代表的な不一致選挙区（最良実験のもの）
        best_dc = best_district["district_comp"]
        if best_dc and best_dc["mismatches"]:
            print(f"■ 不一致選挙区の詳細 ({best_district['exp']['label']}, "
                  f"一致率{best_dc['match_rate']:.1%})")
            print()

            # marginでソート（接戦順）
            sorted_mismatches = sorted(best_dc["mismatches"], key=lambda m: m["margin"])
            for m in sorted_mismatches[:30]:
                pred_ja = PARTY_NAMES_JA.get(m["predicted"], m["predicted"])
                actual_ja = PARTY_NAMES_JA.get(m["actual"], m["actual"])
                print(f"  {m['district_name']:12s}  予測:{pred_ja:8s} → 実際:{actual_ja:8s}  "
                      f"(予測margin={m['margin']}票)")

            if len(sorted_mismatches) > 30:
                print(f"  ... 他 {len(sorted_mismatches) - 30}件")

            print()

        # --- 政党別的中率 ---
        print("■ 政党別的中率（予測した政党が実際に当選した割合）")
        print()

        # 主要政党の列
        pa_parties = ["ldp", "chudo", "ishin", "dpfp", "independent", "genzei", "jcp"]
        pa_header = f"{'実験':22s}"
        for p in pa_parties:
            name = PARTY_NAMES_JA.get(p, p)[:4]
            pa_header += f" {name:>8s}"
        print(pa_header)
        print("-" * (22 + 9 * len(pa_parties)))

        for r in results:
            pa = r["party_accuracy"]
            if pa is None:
                continue
            line = f"{r['exp']['label']:22s}"
            for p in pa_parties:
                if p in pa and pa[p]["predicted"] > 0:
                    line += f" {pa[p]['accuracy']:>5.0%}({pa[p]['predicted']:>3d})"
                else:
                    line += f"     {'--':>6s}"
            print(line)

        print()
        print("  ※ カッコ内は予測件数。例: 95%(200) = 200区で予測し95%的中")
        print()

        # --- 確信度別的中率 ---
        has_conf = any(r["confidence_accuracy"] is not None for r in results)
        if has_conf:
            print("■ 確信度別的中率（ペルソナ平均確信度ビン別の選挙区的中率）")
            print()

            for r in results:
                ca = r["confidence_accuracy"]
                if ca is None:
                    continue
                print(f"  [{r['exp']['label']}]")
                for bin_label, data in ca.items():
                    if data["total"] > 0:
                        bar = "#" * int(data["accuracy"] * 20)
                        print(f"    {bin_label:20s}  {data['accuracy']:>5.1%}  "
                              f"({data['correct']:>3d}/{data['total']:>3d}区)  {bar}")
                    else:
                        print(f"    {bin_label:20s}  {'--':>5s}  (  0区)")
                print()

        # --- LLM投票者のみの的中率 ---
        has_llm = any(r["llm_only"] is not None for r in results)
        if has_llm:
            print("■ LLM投票者のみの的中率（投票先をLLMが決定した票のみで勝者を再集計）")
            print()

            llm_header = f"{'実験':22s} {'共通区':>5s} {'一致':>5s} {'的中率':>7s}  {'LLM政党別的中率':s}"
            print(llm_header)
            print("-" * 90)

            for r in results:
                lo = r["llm_only"]
                if lo is None:
                    continue
                # 主要政党の的中率サマリー
                pa_summary_parts = []
                for p in ["ldp", "chudo", "ishin", "dpfp"]:
                    pa = lo["party_accuracy"].get(p)
                    if pa and pa["predicted"] > 0:
                        name = PARTY_NAMES_JA.get(p, p)[:4]
                        pa_summary_parts.append(f"{name}{pa['accuracy']:.0%}({pa['predicted']})")
                pa_summary = " ".join(pa_summary_parts)

                print(f"{r['exp']['label']:22s} {lo['total']:>5d} {lo['correct']:>5d} "
                      f"{lo['accuracy']:>6.1%}  {pa_summary}")

            print()

            # 詳細: district_results.csvの勝者 vs LLM再集計の勝者が異なるケース
            for r in results:
                lo = r["llm_only"]
                dc = r["district_comp"]
                if lo is None or dc is None:
                    continue

                # district_results.csvの的中率とLLM再集計の的中率の比較
                csv_rate = dc["match_rate"]
                llm_rate = lo["accuracy"]
                diff = llm_rate - csv_rate
                if abs(diff) > 0.001:
                    print(f"  [{r['exp']['label']}] "
                          f"CSV集計的中率={csv_rate:.1%} vs LLM再集計的中率={llm_rate:.1%} "
                          f"(差={diff:+.1%})")

            print()

        # --- 接戦区精度 ---
        has_bg = any(r.get("battleground") is not None for r in results)
        if has_bg:
            print("■ 接戦区精度（予測margin下位25%の選挙区での的中率）")
            print()
            bg_header = f"{'実験':22s} {'接戦区数':>6s} {'的中':>5s} {'接戦的中率':>8s} {'安全区的中率':>10s}"
            print(bg_header)
            print("-" * 70)
            for r in results:
                bg = r.get("battleground")
                if bg is None:
                    continue
                print(f"{r['exp']['label']:22s} {bg['battleground_count']:>6d} "
                      f"{bg['battleground_correct']:>5d} {bg['battleground_accuracy']:>7.1%} "
                      f"{bg['safe_accuracy']:>10.1%}")
            print()

        # --- 比例代表議席比較 ---
        has_pr = any(r.get("pr_seats") for r in results)
        if has_pr:
            print("■ 比例代表 政党別議席数比較")
            print()
            pr_parties = ["ldp", "chudo", "ishin", "dpfp", "sansei", "mirai", "jcp", "reiwa"]
            pr_header = f"{'実験':22s}"
            for p in pr_parties:
                name = PARTY_NAMES_JA.get(p, p)[:4]
                pr_header += f" {name:>5s}"
            pr_header += f" {'合計':>5s} {'PR_MAE':>7s}"
            print(pr_header)
            print("-" * (22 + 6 * len(pr_parties) + 14))

            # 実際のPR結果行
            actual_pr_total = sum(ACTUAL_PR_SEATS.values())
            line = f"{'★ 実際の結果':22s}"
            for p in pr_parties:
                line += f" {ACTUAL_PR_SEATS.get(p, 0):>5d}"
            line += f" {actual_pr_total:>5d}       "
            print(line)
            print("-" * (22 + 6 * len(pr_parties) + 14))

            for r in results:
                pr = r.get("pr_seats")
                if not pr:
                    continue
                pr_total = sum(pr.values())
                pr_mae = calc_smd_mae(pr, ACTUAL_PR_SEATS)
                line = f"{r['exp']['label']:22s}"
                for p in pr_parties:
                    line += f" {pr.get(p, 0):>5d}"
                line += f" {pr_total:>5d} {pr_mae:>7.1f}"
                print(line)
            print()

        # --- スイング層分析 ---
        has_swing = any(r.get("swing_analysis") is not None for r in results)
        if has_swing:
            print("■ スイング層別の投票先分布（LDP票率）")
            print()
            swing_header = f"{'実験':22s} {'low':>8s} {'moderate':>8s} {'mod_high':>8s} {'high':>8s}"
            print(swing_header)
            print("-" * 60)
            for r in results:
                sa = r.get("swing_analysis")
                if sa is None:
                    continue
                line = f"{r['exp']['label']:22s}"
                for level in ["low", "moderate", "moderate_high", "high"]:
                    data = sa.get(level, {})
                    total = data.get("total_voters", 0)
                    ldp_votes = data.get("party_votes", {}).get("ldp", 0)
                    if total > 0:
                        line += f" {ldp_votes/total:>6.0%}  "
                    else:
                        line += f"   {'--':>5s} "
                print(line)
            print()
            print("  ※ low=固定票層、moderate=やや浮動、moderate_high=浮動気味、high=完全浮動")
            print()

        # --- 棄権パターン分析 ---
        has_abs = any(r.get("abstention_analysis") is not None for r in results)
        if has_abs:
            print("■ 棄権パターン分析")
            print()
            for r in results:
                aa = r.get("abstention_analysis")
                if aa is None:
                    continue
                print(f"  [{r['exp']['label']}] "
                      f"全{aa['total_personas']}人中 {aa['total_abstained']}人棄権 "
                      f"({aa['abstention_rate']:.1%})")
                top_reasons = sorted(aa["reason_counts"].items(),
                                     key=lambda x: -x[1])[:5]
                for reason, count in top_reasons:
                    print(f"    {reason}: {count}人")
                print()

        # --- 全289選挙区の的中/外れ一覧 ---
        print("■ 全選挙区 的中/外れ一覧（各実験）")
        print()

        for r in results:
            fdl = r["full_district_list"]
            if fdl is None:
                continue
            hits = sum(1 for d in fdl if d["hit"])
            total = len(fdl)
            print(f"  [{r['exp']['label']}] {hits}/{total}区的中 ({hits/total:.1%})")
            print()

            header_d = f"    {'選挙区':14s} {'予測':10s} {'実際':10s} {'結果':>4s} {'margin':>7s}"
            print(header_d)
            print("    " + "-" * 55)

            for d in fdl:
                pred_ja = PARTY_NAMES_JA.get(d["predicted"], d["predicted"])
                actual_ja = PARTY_NAMES_JA.get(d["actual"], d["actual"])
                mark = "O" if d["hit"] else "X"
                print(f"    {d['district_name']:14s} {pred_ja:10s} {actual_ja:10s} "
                      f"{mark:>4s} {d['margin']:>7d}")

            print()

    # --- 主要な知見 ---
    print("■ 主な知見")
    print()

    best = ranked[0]
    print(f"  1. 最も精度が高かったのは {best['exp']['label']} (総誤差{best['total_abs']}席)")

    # LDP予測
    ldp_best = min(results, key=lambda r: abs(r["ldp_diff"]))
    print(f"  2. LDP議席を最も正確に予測したのは {ldp_best['exp']['label']} "
          f"(予測{ldp_best['smd'].get('ldp', 0)} vs 実際{ACTUAL_SMD_SEATS['ldp']}, "
          f"差{ldp_best['ldp_diff']:+d})")

    # 投票率
    turnout_best = min(results, key=lambda r: abs(r["turnout_diff"]))
    print(f"  3. 投票率を最も正確に予測したのは {turnout_best['exp']['label']} "
          f"(予測{turnout_best['turnout']:.2%} vs 実際{ACTUAL_TURNOUT:.2%})")

    # 全実験の過半数予測
    majority_results = [(r["exp"]["label"], r["majority_correct"]) for r in results]
    correct_count = sum(1 for _, c in majority_results if c)
    print(f"  4. 自民単独過半数の予測: {correct_count}/{len(majority_results)}実験が正解")
    for label, correct in majority_results:
        mark = "O (正解)" if correct else "X (不正解)"
        print(f"     - {label}: {mark}")

    # 中道の過大評価
    print(f"  5. 全実験が中道改革連合を大幅に過大予測 "
          f"(実際{ACTUAL_SMD_SEATS['chudo']}席に対し予測{min(r['smd'].get('chudo', 0) for r in results)}"
          f"-{max(r['smd'].get('chudo', 0) for r in results)}席)")

    print()
    print("=" * 80)

    # ============================================================
    # Markdownレポート生成
    # ============================================================

    md_lines = []
    md_lines.append("# シミュレーション実験 vs 実選挙結果 比較レポート")
    md_lines.append("")
    md_lines.append("## 第51回衆議院議員総選挙（2026年2月8日投開票）")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # 実際の結果
    md_lines.append("## 1. 実際の選挙結果")
    md_lines.append("")
    md_lines.append(f"- **投票率**: {ACTUAL_TURNOUT:.2%}")
    md_lines.append(f"- **自民党**: 316議席（小選挙区249 + 比例67）→ 単独で2/3超の歴史的大勝")
    md_lines.append(f"- **中道改革連合**: 49議席（小選挙区7 + 比例42）→ 惨敗")
    md_lines.append("")
    md_lines.append("| 政党 | 小選挙区 | 比例代表 | 合計 |")
    md_lines.append("|------|---------|---------|------|")
    for p in ["ldp", "chudo", "ishin", "dpfp", "sansei", "mirai", "jcp", "reiwa", "genzei", "independent"]:
        name = PARTY_NAMES_JA.get(p, p)
        smd = ACTUAL_SMD_SEATS.get(p, 0)
        pr = ACTUAL_PR_SEATS.get(p, 0)
        total = ACTUAL_TOTAL_SEATS.get(p, 0)
        md_lines.append(f"| {name} | {smd} | {pr} | {total} |")
    md_lines.append(f"| **合計** | **289** | **176** | **465** |")
    md_lines.append("")
    md_lines.append("出典: NHK選挙速報, 日本経済新聞, 時事通信, zeimo.jp")
    md_lines.append("")

    # 比較表
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 2. 小選挙区 政党別議席数比較")
    md_lines.append("")
    md_lines.append("| 実験 | 方式 | 投票率 | 自民 | 中道 | 維新 | 国民 | 共産 | その他 |")
    md_lines.append("|------|------|--------|------|------|------|------|------|--------|")

    others_actual = sum(v for k, v in ACTUAL_SMD_SEATS.items()
                        if k not in ("ldp", "chudo", "ishin", "dpfp", "jcp"))
    md_lines.append(
        f"| **実際の結果** | - | **{ACTUAL_TURNOUT:.1%}** | **{ACTUAL_SMD_SEATS['ldp']}** | "
        f"**{ACTUAL_SMD_SEATS['chudo']}** | **{ACTUAL_SMD_SEATS['ishin']}** | "
        f"**{ACTUAL_SMD_SEATS['dpfp']}** | **{ACTUAL_SMD_SEATS['jcp']}** | **{others_actual}** |"
    )

    for r in results:
        smd = r["smd"]
        others = sum(v for k, v in smd.items()
                     if k not in ("ldp", "chudo", "ishin", "dpfp", "jcp"))
        md_lines.append(
            f"| {r['exp']['label']} | {r['exp']['method']} | {r['turnout']:.1%} | "
            f"{smd.get('ldp', 0)} | {smd.get('chudo', 0)} | {smd.get('ishin', 0)} | "
            f"{smd.get('dpfp', 0)} | {smd.get('jcp', 0)} | {others} |"
        )
    md_lines.append("")

    # 差分表
    md_lines.append("## 3. 議席数差分（実験 - 実際）")
    md_lines.append("")
    md_lines.append("| 実験 | 自民 | 中道 | 維新 | 国民 | 共産 | 総絶対誤差 |")
    md_lines.append("|------|------|------|------|------|------|-----------|")

    for r in results:
        smd = r["smd"]
        diffs = {
            "ldp": smd.get("ldp", 0) - ACTUAL_SMD_SEATS["ldp"],
            "chudo": smd.get("chudo", 0) - ACTUAL_SMD_SEATS["chudo"],
            "ishin": smd.get("ishin", 0) - ACTUAL_SMD_SEATS["ishin"],
            "dpfp": smd.get("dpfp", 0) - ACTUAL_SMD_SEATS["dpfp"],
            "jcp": smd.get("jcp", 0) - ACTUAL_SMD_SEATS["jcp"],
        }
        md_lines.append(
            f"| {r['exp']['label']} | {diffs['ldp']:+d} | {diffs['chudo']:+d} | "
            f"{diffs['ishin']:+d} | {diffs['dpfp']:+d} | {diffs['jcp']:+d} | "
            f"{r['total_abs']} |"
        )
    md_lines.append("")

    # ランキング
    md_lines.append("## 4. 精度ランキング（議席総絶対誤差の小さい順）")
    md_lines.append("")
    md_lines.append("| 順位 | 実験 | 総誤差 | MAE | LDP差 | 投票率差 | 区一致率 | 過半数予測 |")
    md_lines.append("|------|------|--------|-----|-------|---------|---------|-----------|")

    for i, r in enumerate(ranked, 1):
        majority_mark = "O" if r["majority_correct"] else "X"
        dc = r["district_comp"]
        match_str = f"{dc['match_rate']:.1%}" if dc else "N/A"
        md_lines.append(
            f"| {i} | {r['exp']['label']} | {r['total_abs']}席 | {r['mae']:.1f} | "
            f"{r['ldp_diff']:+d} | {r['turnout_diff']:+.2%} | {match_str} | {majority_mark} |"
        )
    md_lines.append("")

    # 選挙区レベル比較セクション
    if has_district_data:
        md_lines.append("## 4.5. 選挙区レベルの当選政党一致率")
        md_lines.append("")
        md_lines.append("| 実験 | 共通区数 | 一致 | 不一致 | 一致率 |")
        md_lines.append("|------|---------|------|--------|--------|")

        for r in results:
            dc = r["district_comp"]
            if dc is None:
                continue
            md_lines.append(
                f"| {r['exp']['label']} | {dc['common']} | {dc['matches']} | "
                f"{dc['common'] - dc['matches']} | **{dc['match_rate']:.1%}** |"
            )
        md_lines.append("")

        # 地域別一致率テーブル
        md_lines.append("### 地域別一致率")
        md_lines.append("")

        region_md_header = "| 地域 |"
        region_md_sep = "|------|"
        for r in results:
            if r["district_comp"] is not None:
                region_md_header += f" {r['exp']['id']} |"
                region_md_sep += "------|"
        md_lines.append(region_md_header)
        md_lines.append(region_md_sep)

        REGION_ORDER = ["北海道", "東北", "北関東", "南関東", "東京", "北陸信越",
                        "東海", "近畿", "中国", "四国", "九州", "沖縄"]

        for region in REGION_ORDER:
            line = f"| {region} |"
            for r in results:
                dc = r["district_comp"]
                if dc is None:
                    continue
                rs = dc["region_stats"].get(region)
                if rs and rs["total"] > 0:
                    rate = rs["match"] / rs["total"]
                    line += f" {rate:.0%} |"
                else:
                    line += " -- |"
            md_lines.append(line)
        md_lines.append("")

        # 不一致パターン
        md_lines.append("### 不一致パターン（予測→実際、全実験合計）")
        md_lines.append("")
        md_lines.append("| パターン | 件数 |")
        md_lines.append("|---------|------|")

        all_patterns = Counter()
        for r in results:
            dc = r["district_comp"]
            if dc is None:
                continue
            all_patterns += dc["mismatch_patterns"]

        for pattern, count in all_patterns.most_common(10):
            pred, actual = pattern.split("→")
            pred_ja = PARTY_NAMES_JA.get(pred, pred)
            actual_ja = PARTY_NAMES_JA.get(actual, actual)
            md_lines.append(f"| {pred_ja} → {actual_ja} | {count} |")
        md_lines.append("")

    # 政党別的中率セクション
    if has_district_data:
        md_lines.append("## 5. 政党別的中率")
        md_lines.append("")
        md_lines.append("予測した政党が実際に当選した割合。カッコ内は予測件数。")
        md_lines.append("")

        pa_parties = ["ldp", "chudo", "ishin", "dpfp", "independent", "genzei", "jcp"]
        pa_header = "| 実験 |"
        pa_sep = "|------|"
        for p in pa_parties:
            name = PARTY_NAMES_JA.get(p, p)
            pa_header += f" {name} |"
            pa_sep += "------|"
        md_lines.append(pa_header)
        md_lines.append(pa_sep)

        for r in results:
            pa = r["party_accuracy"]
            if pa is None:
                continue
            line = f"| {r['exp']['label']} |"
            for p in pa_parties:
                if p in pa and pa[p]["predicted"] > 0:
                    line += f" {pa[p]['accuracy']:.0%} ({pa[p]['predicted']}) |"
                else:
                    line += " -- |"
            md_lines.append(line)
        md_lines.append("")

    # 確信度別的中率セクション
    has_conf = any(r["confidence_accuracy"] is not None for r in results)
    if has_conf:
        md_lines.append("## 6. 確信度別的中率")
        md_lines.append("")
        md_lines.append("ペルソナの平均確信度を選挙区ごとに集計し、ビン別に選挙区的中率を算出。")
        md_lines.append("")

        for r in results:
            ca = r["confidence_accuracy"]
            if ca is None:
                continue
            md_lines.append(f"### {r['exp']['label']}")
            md_lines.append("")
            md_lines.append("| 確信度ビン | 的中率 | 的中/全 |")
            md_lines.append("|-----------|--------|---------|")
            for bin_label, data in ca.items():
                if data["total"] > 0:
                    md_lines.append(
                        f"| {bin_label} | **{data['accuracy']:.1%}** | "
                        f"{data['correct']}/{data['total']} |"
                    )
                else:
                    md_lines.append(f"| {bin_label} | -- | 0 |")
            md_lines.append("")

    # LLM投票者のみの的中率セクション
    has_llm = any(r["llm_only"] is not None for r in results)
    if has_llm:
        md_lines.append("## 6.5. LLM投票者のみの的中率")
        md_lines.append("")
        md_lines.append("v8a以降のデカップリング方式では、投票参加/棄権はルールベースで決定し、")
        md_lines.append("投票先のみをLLMが予測する。ここではLLM投票者の票のみで選挙区勝者を再集計し、")
        md_lines.append("実際の結果との一致率を算出。")
        md_lines.append("")

        md_lines.append("| 実験 | 共通区 | 一致 | 的中率 | 自民 | 中道 | 維新 | 国民 |")
        md_lines.append("|------|--------|------|--------|------|------|------|------|")

        for r in results:
            lo = r["llm_only"]
            if lo is None:
                continue
            pa = lo["party_accuracy"]
            cells = []
            for p in ["ldp", "chudo", "ishin", "dpfp"]:
                if p in pa and pa[p]["predicted"] > 0:
                    cells.append(f"{pa[p]['accuracy']:.0%} ({pa[p]['predicted']})")
                else:
                    cells.append("--")
            md_lines.append(
                f"| {r['exp']['label']} | {lo['total']} | {lo['correct']} | "
                f"**{lo['accuracy']:.1%}** | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |"
            )

        md_lines.append("")

        # CSV的中率との差異
        diffs_found = False
        for r in results:
            lo = r["llm_only"]
            dc = r["district_comp"]
            if lo is None or dc is None:
                continue
            csv_rate = dc["match_rate"]
            llm_rate = lo["accuracy"]
            diff = llm_rate - csv_rate
            if abs(diff) > 0.001:
                if not diffs_found:
                    md_lines.append("**CSV集計的中率 vs LLM再集計的中率の差異:**")
                    md_lines.append("")
                    diffs_found = True
                md_lines.append(
                    f"- {r['exp']['label']}: CSV={csv_rate:.1%} vs LLM再集計={llm_rate:.1%} "
                    f"(差={diff:+.1%})"
                )
        if diffs_found:
            md_lines.append("")

    # 接戦区精度セクション
    has_bg = any(r.get("battleground") is not None for r in results)
    if has_bg:
        md_lines.append("## 6.6. 接戦区精度")
        md_lines.append("")
        md_lines.append("予測margin下位25%の選挙区（接戦区）での当選政党的中率。")
        md_lines.append("")
        md_lines.append("| 実験 | 接戦区数 | 的中 | 接戦区的中率 | 安全区的中率 |")
        md_lines.append("|------|---------|------|-----------|-----------|")
        for r in results:
            bg = r.get("battleground")
            if bg is None:
                continue
            md_lines.append(
                f"| {r['exp']['label']} | {bg['battleground_count']} | "
                f"{bg['battleground_correct']} | **{bg['battleground_accuracy']:.1%}** | "
                f"{bg['safe_accuracy']:.1%} |"
            )
        md_lines.append("")

    # 比例代表比較セクション
    has_pr = any(r.get("pr_seats") for r in results)
    if has_pr:
        md_lines.append("## 6.7. 比例代表 政党別議席数比較")
        md_lines.append("")
        pr_parties = ["ldp", "chudo", "ishin", "dpfp", "sansei", "mirai", "jcp", "reiwa"]
        pr_header = "| 実験 |"
        pr_sep = "|------|"
        for p in pr_parties:
            name = PARTY_NAMES_JA.get(p, p)
            pr_header += f" {name} |"
            pr_sep += "------|"
        pr_header += " 合計 | PR MAE |"
        pr_sep += "------|------|"
        md_lines.append(pr_header)
        md_lines.append(pr_sep)

        actual_pr_total = sum(ACTUAL_PR_SEATS.values())
        line = "| **実際の結果** |"
        for p in pr_parties:
            line += f" **{ACTUAL_PR_SEATS.get(p, 0)}** |"
        line += f" **{actual_pr_total}** | - |"
        md_lines.append(line)

        for r in results:
            pr = r.get("pr_seats")
            if not pr:
                continue
            pr_total = sum(pr.values())
            pr_mae = calc_smd_mae(pr, ACTUAL_PR_SEATS)
            line = f"| {r['exp']['label']} |"
            for p in pr_parties:
                line += f" {pr.get(p, 0)} |"
            line += f" {pr_total} | {pr_mae:.1f} |"
            md_lines.append(line)
        md_lines.append("")

    # スイング層分析セクション
    has_swing = any(r.get("swing_analysis") is not None for r in results)
    if has_swing:
        md_lines.append("## 6.8. スイング層別の投票先分布")
        md_lines.append("")
        md_lines.append("swing_level別のLDP票率。lowは固定票層、highは完全浮動層。")
        md_lines.append("")
        md_lines.append("| 実験 | low | moderate | moderate_high | high |")
        md_lines.append("|------|-----|---------|--------------|------|")
        for r in results:
            sa = r.get("swing_analysis")
            if sa is None:
                continue
            cells = []
            for level in ["low", "moderate", "moderate_high", "high"]:
                data = sa.get(level, {})
                total = data.get("total_voters", 0)
                ldp = data.get("party_votes", {}).get("ldp", 0)
                if total > 0:
                    cells.append(f"{ldp/total:.0%}")
                else:
                    cells.append("--")
            md_lines.append(
                f"| {r['exp']['label']} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |"
            )
        md_lines.append("")

    # 棄権パターン分析セクション
    has_abs = any(r.get("abstention_analysis") is not None for r in results)
    if has_abs:
        md_lines.append("## 6.9. 棄権パターン分析")
        md_lines.append("")
        md_lines.append("| 実験 | 全ペルソナ | 棄権数 | 棄権率 | 主な棄権理由 |")
        md_lines.append("|------|----------|--------|--------|------------|")
        for r in results:
            aa = r.get("abstention_analysis")
            if aa is None:
                continue
            top3 = sorted(aa["reason_counts"].items(), key=lambda x: -x[1])[:3]
            reasons_str = "; ".join(f"{reason}({count})" for reason, count in top3)
            md_lines.append(
                f"| {r['exp']['label']} | {aa['total_personas']} | {aa['total_abstained']} | "
                f"{aa['abstention_rate']:.1%} | {reasons_str} |"
            )
        md_lines.append("")

    # 全選挙区的中/外れ一覧セクション
    if has_district_data:
        md_lines.append("## 7. 全選挙区 的中/外れ一覧")
        md_lines.append("")

        for r in results:
            fdl = r["full_district_list"]
            if fdl is None:
                continue
            hits = sum(1 for d in fdl if d["hit"])
            total = len(fdl)
            md_lines.append(f"### {r['exp']['label']} ({hits}/{total}区的中, {hits/total:.1%})")
            md_lines.append("")
            md_lines.append("| 選挙区 | 予測 | 実際 | 結果 | margin |")
            md_lines.append("|--------|------|------|------|--------|")
            for d in fdl:
                pred_ja = PARTY_NAMES_JA.get(d["predicted"], d["predicted"])
                actual_ja = PARTY_NAMES_JA.get(d["actual"], d["actual"])
                mark = "O" if d["hit"] else "X"
                md_lines.append(
                    f"| {d['district_name']} | {pred_ja} | {actual_ja} | "
                    f"{mark} | {d['margin']} |"
                )
            md_lines.append("")

    # 知見
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 8. 主な知見")
    md_lines.append("")

    md_lines.append(f"### 精度")
    md_lines.append(f"- 最も精度が高かったのは **{best['exp']['label']}** (総誤差{best['total_abs']}席)")
    md_lines.append(f"- LDP議席を最も正確に予測: **{ldp_best['exp']['label']}** "
                    f"(予測{ldp_best['smd'].get('ldp', 0)} vs 実際{ACTUAL_SMD_SEATS['ldp']}, "
                    f"差{ldp_best['ldp_diff']:+d})")
    md_lines.append(f"- 投票率を最も正確に予測: **{turnout_best['exp']['label']}** "
                    f"(予測{turnout_best['turnout']:.2%} vs 実際{ACTUAL_TURNOUT:.2%})")
    md_lines.append("")

    md_lines.append("### 自民単独過半数の予測")
    md_lines.append(f"- {correct_count}/{len(majority_results)}実験が正解")
    for label, correct in majority_results:
        mark = "O (正解)" if correct else "X (不正解)"
        md_lines.append(f"  - {label}: {mark}")
    md_lines.append("")

    md_lines.append("### 体系的バイアス")
    md_lines.append(f"- **全実験が中道改革連合の議席を大幅に過大予測**: "
                    f"実際{ACTUAL_SMD_SEATS['chudo']}席に対し、"
                    f"予測は{min(r['smd'].get('chudo', 0) for r in results)}"
                    f"~{max(r['smd'].get('chudo', 0) for r in results)}席")
    md_lines.append(f"- **全実験がLDPの議席を過少予測**: "
                    f"実際{ACTUAL_SMD_SEATS['ldp']}席に対し、"
                    f"予測は{min(r['smd'].get('ldp', 0) for r in results)}"
                    f"~{max(r['smd'].get('ldp', 0) for r in results)}席")

    chudo_overest = [(r["exp"]["label"], r["smd"].get("chudo", 0) - ACTUAL_SMD_SEATS["chudo"]) for r in results]
    md_lines.append(f"- 中道の過大予測は特にルールベース系・メモリ系で顕著 "
                    f"（v10b: +{max(d for _, d in chudo_overest)}席）")
    md_lines.append("")

    md_lines.append("### 手法別の評価")
    md_lines.append("- **キャリブレーションLLM (v8a)**: LDP予測が最も正確だが、中道も過大予測")
    md_lines.append("- **LLM全ペルソナ (v4b)**: LDP予測は近いが、投票率が大幅に過大 (79.5%)")
    md_lines.append("- **ルールベース (v2)**: 投票率は正確だが、LDP過少/中道過大のバイアスが大きい")
    md_lines.append("- **ハイブリッド (v9a)**: ルールベースに近い結果、接戦区LLMの効果は限定的")
    md_lines.append("- **人口統計/メモリ (v10a/b)**: 中道過大バイアスが最も大きい")
    md_lines.append("")

    md_lines.append("### 教訓")
    md_lines.append("1. LLMは中道・リベラル方向へのバイアスを持つ (全実験で確認)")
    md_lines.append("2. キャリブレーション (v8a) が最もバイアスを緩和できた")
    md_lines.append("3. ルールベースの支持率データ自体が2024年選挙ベースであり、"
                    "2026年の自民大勝トレンドを反映できていなかった")
    md_lines.append("4. 投票率予測はデカップリング方式 (v8a) で改善されたが、"
                    "投票率と議席数の両方を正確に予測した実験はなかった")
    md_lines.append("")

    # 書き出し
    report_path = REPORT_DIR / "comparison_with_actual.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"Markdownレポートを保存しました: {report_path}")
    print()


if __name__ == "__main__":
    main()
