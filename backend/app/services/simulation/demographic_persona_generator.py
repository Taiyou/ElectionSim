"""
人口統計ベースのペルソナ生成（v10a/v10b共通）

15アーキタイプを廃止し、国勢調査の人口統計データ（年齢分布・性別比率・産業構造・
所得水準・大卒率・都市化分類）から直接ペルソナを生成する。
投票行動パラメータ（投票率・イデオロギー）は人口統計属性からルールベースで算出。
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path

_FILE_DIR = Path(__file__).resolve().parent  # .../simulation/
DATA_DIR = _FILE_DIR.parent.parent / "data"  # .../app/data/
_BACKEND_DIR = _FILE_DIR.parent.parent.parent  # .../backend/ or /app/
BASE_DIR = _BACKEND_DIR.parent
PERSONA_DIR = BASE_DIR / "persona_data"


@dataclass
class DemographicPersona:
    """人口統計ベースのペルソナ（v10）"""
    persona_id: str
    district_id: str
    age: int
    gender: str                  # 男性/女性
    occupation: str
    industry_sector: str         # primary/secondary/tertiary
    household_type: str          # single/couple/nuclear_family/three_generation/other
    income_bracket: str          # 低/中/高
    education_level: str         # 高卒以下/専門卒/大卒以上
    urbanization_level: str      # 大都市/中核市/地方都市/農村部
    political_engagement: str    # high/moderate/low
    turnout_probability: float   # 0.0-1.0
    top_concerns: list[str] = field(default_factory=list)
    information_sources: list[str] = field(default_factory=list)
    party_affinity: str = "支持なし"
    ideology: str = "中道"


# ---------------------------------------------------------------------------
# 年齢帯域定義（CSVのカラム名に対応）
# ---------------------------------------------------------------------------
AGE_BANDS = [
    ("年齢_18〜29歳", 18, 29),
    ("年齢_30〜39歳", 30, 39),
    ("年齢_40〜49歳", 40, 49),
    ("年齢_50〜59歳", 50, 59),
    ("年齢_60〜69歳", 60, 69),
    ("年齢_70歳以上", 70, 90),
]

# ---------------------------------------------------------------------------
# 産業セクター別の職業プール
# ---------------------------------------------------------------------------
OCCUPATION_BY_SECTOR = {
    "primary": {
        "young": ["農業従事者", "酪農業", "漁業従事者", "林業従事者"],
        "middle": ["農業経営者", "酪農経営", "漁船船長", "林業経営"],
        "senior": ["農業（兼業）", "農業経営者", "漁業従事者"],
    },
    "secondary": {
        "young": ["工場勤務", "建設作業員", "電機メーカー社員", "自動車工場員"],
        "middle": ["工場管理職", "建設会社管理職", "製造業エンジニア", "品質管理"],
        "senior": ["工場パート", "製造業シルバー人材"],
    },
    "tertiary": {
        "young": [
            "会社員（IT）", "会社員（営業）", "会社員（事務）", "販売員",
            "飲食業", "介護職", "看護師", "フリーランス",
        ],
        "middle": [
            "会社員（管理職）", "会社員（営業）", "公務員", "教員",
            "医療従事者", "ITコンサル", "自営業", "不動産業",
        ],
        "senior": [
            "年金受給者", "シルバー人材", "パート", "介護施設勤務",
        ],
    },
}

# 大学生用（18-25歳限定）
STUDENT_OCCUPATIONS = ["大学生", "大学院生"]

# ---------------------------------------------------------------------------
# 所得分布（所得水準 → 個人レベルの振り分け）
# ---------------------------------------------------------------------------
INCOME_DIST = {
    "高": {"高": 0.45, "中": 0.40, "低": 0.15},
    "中": {"高": 0.20, "中": 0.50, "低": 0.30},
    "低": {"高": 0.10, "中": 0.30, "低": 0.60},
}

# ---------------------------------------------------------------------------
# 世帯タイプマッピング（CSVカラム名 → 内部キー）
# ---------------------------------------------------------------------------
HOUSEHOLD_COL_MAP = {
    "世帯_単身": "single",
    "世帯_夫婦のみ": "couple",
    "世帯_核家族": "nuclear_family",
    "世帯_三世代": "three_generation",
    "世帯_その他": "other",
}

# ---------------------------------------------------------------------------
# 関心事項（年齢帯域ベース）
# ---------------------------------------------------------------------------
CONCERNS_BY_AGE = {
    "young": ["雇用・賃金", "物価高対策", "教育・子育て", "SNS規制"],
    "middle": ["物価高対策", "社会保障", "教育・子育て", "税制改革", "経済成長"],
    "senior": ["年金", "医療・介護", "社会保障", "防災", "地方創生"],
}

# ---------------------------------------------------------------------------
# 情報源（年齢ベース）
# ---------------------------------------------------------------------------
INFO_SOURCES_BY_AGE = {
    "young": ["SNS", "YouTube", "ネットニュース"],
    "middle": ["テレビ", "ネットニュース", "新聞", "SNS"],
    "senior": ["テレビ", "新聞", "地域組織", "ラジオ"],
}


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------
def _weighted_choice(options: dict[str, float], rng: random.Random) -> str:
    """加重ランダム選択"""
    items = list(options.keys())
    weights = [max(0, options[k]) for k in items]
    total = sum(weights)
    if total <= 0:
        return items[0] if items else ""
    return rng.choices(items, weights=weights, k=1)[0]


def _age_group(age: int) -> str:
    """年齢 → young/middle/senior の分類"""
    if age < 30:
        return "young"
    elif age < 60:
        return "middle"
    else:
        return "senior"


def _compute_turnout_probability(
    age: int,
    education_level: str,
    income_bracket: str,
    industry_sector: str,
    urbanization: str,
    weather_modifier: float,
) -> float:
    """人口統計属性から投票率をルールベースで算出"""
    # 年齢別基礎投票率
    if age <= 29:
        base = 0.35
    elif age <= 39:
        base = 0.50
    elif age <= 49:
        base = 0.55
    elif age <= 59:
        base = 0.60
    elif age <= 69:
        base = 0.70
    elif age <= 74:
        base = 0.75
    else:
        base = 0.65

    # 修正項
    if education_level == "大卒以上":
        base += 0.05
    if income_bracket == "低":
        base -= 0.10
    elif income_bracket == "高":
        base += 0.05
    if industry_sector == "primary":
        base += 0.05
    if urbanization in ("大都市", "大都市中心"):
        base -= 0.03

    base += weather_modifier
    return max(0.05, min(0.95, base))


def _compute_ideology(
    age: int,
    industry_sector: str,
    education_level: str,
    income_bracket: str,
    rng: random.Random,
) -> str:
    """人口統計属性からイデオロギーを確率的に算出"""
    # 基礎確率
    probs = {"保守": 0.30, "中道": 0.35, "リベラル": 0.25, "無関心": 0.10}

    # 年齢修正
    if age <= 29:
        probs["リベラル"] += 0.10
        probs["無関心"] += 0.10
        probs["保守"] -= 0.10
    elif age >= 65:
        probs["保守"] += 0.15
        probs["リベラル"] -= 0.10

    # 産業修正
    if industry_sector == "primary":
        probs["保守"] += 0.15
        probs["リベラル"] -= 0.10
    elif industry_sector == "tertiary":
        probs["リベラル"] += 0.05

    # 教育修正
    if education_level == "大卒以上":
        probs["リベラル"] += 0.05
        probs["無関心"] -= 0.05

    # 所得修正
    if income_bracket == "低":
        probs["リベラル"] += 0.05
    elif income_bracket == "高":
        probs["保守"] += 0.05

    # 負値防止 & 正規化
    probs = {k: max(0.01, v) for k, v in probs.items()}
    return _weighted_choice(probs, rng)


def _compute_engagement(age: int, education_level: str, rng: random.Random) -> str:
    """政治関心度を算出"""
    probs = {"high": 0.25, "moderate": 0.45, "low": 0.30}
    if age >= 60:
        probs["high"] += 0.15
        probs["low"] -= 0.10
    elif age <= 29:
        probs["low"] += 0.15
        probs["high"] -= 0.10
    if education_level == "大卒以上":
        probs["high"] += 0.05
        probs["low"] -= 0.05
    probs = {k: max(0.01, v) for k, v in probs.items()}
    return _weighted_choice(probs, rng)


def _get_weather_impact(prefecture: str) -> float:
    """都道府県名から2/8大雪の影響度を返す（persona_generator.pyと同一ロジック）"""
    heavy_snow = ["北海道", "青森県", "秋田県", "山形県", "新潟県", "富山県", "石川県", "福井県"]
    moderate_snow = ["岩手県", "宮城県", "福島県", "長野県", "鳥取県", "島根県"]
    if any(prefecture.startswith(p.rstrip("県都府")) for p in heavy_snow) or prefecture in heavy_snow:
        return -0.10
    if any(prefecture.startswith(p.rstrip("県都府")) for p in moderate_snow) or prefecture in moderate_snow:
        return -0.05
    return 0.0


# ---------------------------------------------------------------------------
# データ読み込み
# ---------------------------------------------------------------------------
def load_district_data() -> list[dict]:
    """選挙区別データを読み込む"""
    csv_path = PERSONA_DIR / "districts" / "all_districts_persona_data.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_candidates() -> dict[str, list[dict]]:
    """候補者データを選挙区ごとに整理して読み込む"""
    csv_path = DATA_DIR / "candidates.csv"
    candidates_by_district = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = f"{row['prefecture_code'].zfill(2)}_{row['district_number']}"
            candidates_by_district.setdefault(key, []).append(row)
    return candidates_by_district


# ---------------------------------------------------------------------------
# メイン生成関数
# ---------------------------------------------------------------------------
def generate_demographic_personas_for_district(
    district_row: dict,
    num_personas: int = 100,
    seed: int | None = None,
    weather_modifier_override: float | None = None,
) -> list[DemographicPersona]:
    """国勢調査データから直接ペルソナを生成する（アーキタイプ不使用）"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"

    if seed is not None:
        rng = random.Random(seed + hash(district_id) % 10000)
    else:
        rng = random.Random()

    # --- 選挙区の人口統計分布を読み込み ---

    # 年齢分布
    age_dist = {}
    for col, lo, hi in AGE_BANDS:
        age_dist[col] = float(district_row.get(col, 0))

    # 性別比率
    male_ratio = float(district_row.get("男性比率", 0.48))

    # 産業構造
    industry_dist = {
        "primary": float(district_row.get("第一次産業比率", 0.05)),
        "secondary": float(district_row.get("第二次産業比率", 0.20)),
        "tertiary": float(district_row.get("第三次産業比率", 0.75)),
    }

    # 世帯構成
    household_dist = {}
    for col, key in HOUSEHOLD_COL_MAP.items():
        household_dist[key] = float(district_row.get(col, 0.20))

    # 所得水準
    income_level = district_row.get("所得水準", "中")
    income_dist = INCOME_DIST.get(income_level, INCOME_DIST["中"])

    # 学歴
    univ_rate = float(district_row.get("大卒率", 0.30))
    edu_dist = {
        "大卒以上": univ_rate,
        "専門卒": min(0.20, (1 - univ_rate) * 0.30),
        "高卒以下": max(0.0, 1 - univ_rate - min(0.20, (1 - univ_rate) * 0.30)),
    }

    # 都市化分類
    urbanization = district_row.get("都市化分類", "地方都市")

    # 天候修正（APIデータ優先、なければ静的ロジック）
    if weather_modifier_override is not None:
        weather_mod = weather_modifier_override
    else:
        weather_mod = _get_weather_impact(district_row.get("都道府県", ""))

    # 政党支持率分布
    party_support = {
        "ldp": float(district_row.get("支持率_自民党", 0.30)),
        "chudo": float(district_row.get("支持率_立憲民主党", 0.15)),
        "ishin": float(district_row.get("支持率_維新", 0.08)),
        "dpfp": float(district_row.get("支持率_国民民主党", 0.08)),
        "jcp": float(district_row.get("支持率_共産党", 0.05)),
        "reiwa": float(district_row.get("支持率_れいわ", 0.03)),
        "sansei": float(district_row.get("支持率_参政党", 0.03)),
        "その他": float(district_row.get("支持率_その他", 0.15)),
        "支持なし": float(district_row.get("浮動票率", 0.30)),
    }

    # 地域課題
    regional_issues = [
        district_row.get("主要課題1", ""),
        district_row.get("主要課題2", ""),
        district_row.get("主要課題3", ""),
    ]
    regional_issues = [i for i in regional_issues if i]

    # --- ペルソナ生成ループ ---
    personas = []
    for i in range(num_personas):
        # 1. 年齢サンプリング
        age_band_col = _weighted_choice(age_dist, rng)
        for col, lo, hi in AGE_BANDS:
            if col == age_band_col:
                age = rng.randint(lo, hi)
                break
        else:
            age = rng.randint(18, 90)

        # 2. 性別
        gender = "男性" if rng.random() < male_ratio else "女性"

        # 3. 産業セクター
        sector = _weighted_choice(industry_dist, rng)

        # 4. 職業
        age_grp = _age_group(age)
        if age <= 25 and rng.random() < univ_rate * 0.6:
            # 大学生の可能性（18-25歳かつ大卒率に応じた確率）
            occupation = rng.choice(STUDENT_OCCUPATIONS)
        else:
            pool = OCCUPATION_BY_SECTOR.get(sector, {}).get(age_grp, ["会社員"])
            occupation = rng.choice(pool)

        # 5. 世帯タイプ
        household_type = _weighted_choice(household_dist, rng)

        # 6. 所得
        income_bracket = _weighted_choice(income_dist, rng)

        # 7. 学歴
        education_level = _weighted_choice(edu_dist, rng)

        # 8. 投票率
        turnout_prob = _compute_turnout_probability(
            age, education_level, income_bracket, sector, urbanization, weather_mod,
        )

        # 9. イデオロギー
        ideology = _compute_ideology(age, sector, education_level, income_bracket, rng)

        # 10. 政治関心度
        engagement = _compute_engagement(age, education_level, rng)

        # 11. 政党親和性
        party_affinity = _weighted_choice(party_support, rng)

        # 12. 関心事項（地域課題 + 年齢ベース）
        age_concerns = CONCERNS_BY_AGE.get(age_grp, CONCERNS_BY_AGE["middle"])
        combined_concerns = list(set(regional_issues[:2] + age_concerns[:2]))
        rng.shuffle(combined_concerns)
        top_concerns = combined_concerns[:4]

        # 13. 情報源
        info_sources = INFO_SOURCES_BY_AGE.get(age_grp, INFO_SOURCES_BY_AGE["middle"])

        persona = DemographicPersona(
            persona_id=f"{district_id}_{str(i + 1).zfill(3)}",
            district_id=district_id,
            age=age,
            gender=gender,
            occupation=occupation,
            industry_sector=sector,
            household_type=household_type,
            income_bracket=income_bracket,
            education_level=education_level,
            urbanization_level=urbanization,
            political_engagement=engagement,
            turnout_probability=round(turnout_prob, 3),
            top_concerns=top_concerns,
            information_sources=list(info_sources),
            party_affinity=party_affinity,
            ideology=ideology,
        )
        personas.append(persona)

    return personas


def generate_all_demographic_personas(
    seed: int = 42,
    num_per_district: int = 100,
) -> dict[str, list[DemographicPersona]]:
    """全289選挙区の人口統計ペルソナを生成"""
    districts = load_district_data()
    all_personas = {}
    for district_row in districts:
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        personas = generate_demographic_personas_for_district(
            district_row, num_per_district, seed,
        )
        all_personas[district_id] = personas
    return all_personas
