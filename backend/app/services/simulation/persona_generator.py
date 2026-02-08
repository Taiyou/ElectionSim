"""
アーキタイプベースのペルソナ生成

12+3アーキタイプの加重分布に基づき、各選挙区100名のペルソナを生成する。
ルールベースで属性を決定し、LLM呼び出しは不要。
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path

_FILE_DIR = Path(__file__).resolve().parent  # .../simulation/
# Docker: /app/app/services/simulation/ → /app/app/data/
# Local:  .../backend/app/services/simulation/ → .../backend/app/data/
DATA_DIR = _FILE_DIR.parent.parent / "data"

# プロジェクトルート（ローカル用）: backend/ の親
# Docker の場合は /app の親 = / になるが persona_data は使わないので問題なし
_BACKEND_DIR = _FILE_DIR.parent.parent.parent  # .../backend/ or /app/
BASE_DIR = _BACKEND_DIR.parent
PERSONA_DIR = BASE_DIR / "persona_data"


@dataclass
class Persona:
    persona_id: str
    district_id: str
    archetype_id: str
    archetype_name_ja: str
    age: int
    gender: str
    occupation: str
    political_engagement: str
    turnout_probability: float
    swing_tendency: str
    top_concerns: list[str] = field(default_factory=list)
    information_sources: list[str] = field(default_factory=list)
    party_affinity: str = "支持なし"
    ideology: str = "中道"


# 性別配分 (有権者ベース)
GENDER_RATIO = {"男性": 0.48, "女性": 0.52}

# 職業テンプレート（アーキタイプ別）
OCCUPATION_MAP = {
    "urban_young_worker": ["会社員（IT）", "会社員（営業）", "会社員（事務）", "販売員", "飲食業"],
    "suburban_family": ["会社員", "パート", "公務員", "自営業"],
    "middle_aged_salaryman": ["会社員（管理職）", "会社員（営業）", "会社員（技術）"],
    "middle_aged_working_woman": ["パート", "会社員（事務）", "介護職", "看護師", "販売員"],
    "rural_farmer": ["農業", "酪農", "林業", "漁業"],
    "active_elderly": ["年金受給者", "シルバー人材", "農業（兼業）", "パート"],
    "late_elderly": ["年金受給者", "無職"],
    "self_employed": ["飲食店経営", "小売店経営", "建設業", "不動産業", "士業"],
    "public_sector_worker": ["市役所職員", "県庁職員", "教員", "消防士", "警察官"],
    "university_student": ["大学生", "大学院生"],
    "homemaker": ["専業主婦", "専業主夫"],
    "non_regular_worker": ["派遣社員", "契約社員", "アルバイト", "パート"],
    "labor_union_member": ["自動車工場員", "電機メーカー社員", "鉄道会社員", "教員"],
    "tech_worker": ["ソフトウェアエンジニア", "データサイエンティスト", "Webデザイナー", "ITコンサル"],
    "freelance_gig_worker": ["フリーランスエンジニア", "ライター", "デザイナー", "配達員", "動画編集者"],
}

# イデオロギーの基本傾向（アーキタイプ別）
IDEOLOGY_MAP = {
    "urban_young_worker": {"保守": 0.2, "中道": 0.4, "リベラル": 0.3, "無関心": 0.1},
    "suburban_family": {"保守": 0.3, "中道": 0.4, "リベラル": 0.2, "無関心": 0.1},
    "middle_aged_salaryman": {"保守": 0.4, "中道": 0.35, "リベラル": 0.15, "無関心": 0.1},
    "middle_aged_working_woman": {"保守": 0.25, "中道": 0.4, "リベラル": 0.3, "無関心": 0.05},
    "rural_farmer": {"保守": 0.6, "中道": 0.25, "リベラル": 0.1, "無関心": 0.05},
    "active_elderly": {"保守": 0.5, "中道": 0.3, "リベラル": 0.15, "無関心": 0.05},
    "late_elderly": {"保守": 0.55, "中道": 0.3, "リベラル": 0.1, "無関心": 0.05},
    "self_employed": {"保守": 0.45, "中道": 0.3, "リベラル": 0.15, "無関心": 0.1},
    "public_sector_worker": {"保守": 0.2, "中道": 0.35, "リベラル": 0.4, "無関心": 0.05},
    "university_student": {"保守": 0.1, "中道": 0.3, "リベラル": 0.35, "無関心": 0.25},
    "homemaker": {"保守": 0.3, "中道": 0.4, "リベラル": 0.2, "無関心": 0.1},
    "non_regular_worker": {"保守": 0.15, "中道": 0.3, "リベラル": 0.3, "無関心": 0.25},
    "labor_union_member": {"保守": 0.1, "中道": 0.3, "リベラル": 0.55, "無関心": 0.05},
    "tech_worker": {"保守": 0.15, "中道": 0.35, "リベラル": 0.35, "無関心": 0.15},
    "freelance_gig_worker": {"保守": 0.2, "中道": 0.3, "リベラル": 0.25, "無関心": 0.25},
}


def load_archetype_config() -> dict:
    """persona_config.json からアーキタイプ設定を読み込む"""
    config_path = PERSONA_DIR / "persona_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def get_archetype_distribution(district_row: dict) -> dict[str, float]:
    """選挙区データからアーキタイプ分布を取得"""
    # CSVのカラム名からアーキタイプIDへのマッピング
    col_to_id = {
        "ペルソナ_都市部若年勤労者": "urban_young_worker",
        "ペルソナ_郊外子育て世帯": "suburban_family",
        "ペルソナ_中高年会社員": "middle_aged_salaryman",
        "ペルソナ_中高年女性労働者": "middle_aged_working_woman",
        "ペルソナ_農村部農業従事者": "rural_farmer",
        "ペルソナ_高齢年金受給者": "elderly_pensioner",  # active_elderly + late_elderly に分割
        "ペルソナ_自営業者": "self_employed",
        "ペルソナ_公務員": "public_sector_worker",
        "ペルソナ_大学生": "university_student",
        "ペルソナ_専業主婦主夫": "homemaker",
        "ペルソナ_非正規雇用": "non_regular_worker",
        "ペルソナ_労働組合員": "labor_union_member",
    }

    distribution = {}
    for col, archetype_id in col_to_id.items():
        val = float(district_row.get(col, 0))
        if archetype_id == "elderly_pensioner":
            # active_elderly(65-74) と late_elderly(75+) に分割
            distribution["active_elderly"] = round(val * 0.45, 4)
            distribution["late_elderly"] = round(val * 0.55, 4)
        else:
            distribution[archetype_id] = val

    # tech_worker と freelance_gig_worker を都市化レベルに応じて追加
    urban_class = district_row.get("都市化分類", "地方都市")
    if urban_class in ("大都市", "大都市中心"):
        # 都市部: urban_young_worker と non_regular_worker から一部振り分け
        tech_ratio = 0.04
        freelance_ratio = 0.03
    elif urban_class == "中核市":
        tech_ratio = 0.02
        freelance_ratio = 0.02
    else:
        tech_ratio = 0.01
        freelance_ratio = 0.01

    # 既存のアーキタイプから按分
    distribution["tech_worker"] = tech_ratio
    distribution["freelance_gig_worker"] = freelance_ratio

    # 正規化
    total = sum(distribution.values())
    if total > 0:
        distribution = {k: round(v / total, 4) for k, v in distribution.items()}

    return distribution


def weighted_random_choice(options: dict, rng: random.Random | None = None) -> str:
    """加重ランダム選択"""
    items = list(options.keys())
    weights = list(options.values())
    if rng is not None:
        return rng.choices(items, weights=weights, k=1)[0]
    return random.choices(items, weights=weights, k=1)[0]


def generate_personas_for_district(
    district_row: dict,
    archetype_configs: list[dict],
    num_personas: int = 100,
    seed: int | None = None,
    rng: random.Random | None = None,
    weather_modifier_override: float | None = None,
) -> list[Persona]:
    """1つの選挙区に対して指定数のペルソナを生成"""

    district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"

    # スレッドセーフなローカルRNGを使用
    if rng is None:
        if seed is not None:
            rng = random.Random(seed + hash(district_id) % 10000)
        else:
            rng = random.Random()

    # アーキタイプ分布を取得
    distribution = get_archetype_distribution(district_row)

    # アーキタイプ設定をIDで引けるようにする
    archetype_map = {a["id"]: a for a in archetype_configs}

    # 政治傾向データ
    district_party_support = {
        "ldp": float(district_row.get("支持率_自民党", 0.3)),
        "chudo": float(district_row.get("支持率_立憲民主党", 0.15)),
        "ishin": float(district_row.get("支持率_維新", 0.08)),
        "dpfp": float(district_row.get("支持率_国民民主党", 0.08)),
        "jcp": float(district_row.get("支持率_共産党", 0.05)),
        "reiwa": float(district_row.get("支持率_れいわ", 0.03)),
        "sansei": float(district_row.get("支持率_参政党", 0.03)),
        "その他": float(district_row.get("支持率_その他", 0.15)),
        "支持なし": float(district_row.get("浮動票率", 0.30)),
    }

    # 天候修正（APIデータ優先、なければ静的ロジック）
    if weather_modifier_override is not None:
        weather_region = weather_modifier_override
    else:
        weather_region = _get_weather_impact(district_row.get("都道府県", ""))

    personas = []
    for i in range(num_personas):
        # アーキタイプを加重サンプリング
        archetype_id = weighted_random_choice(distribution, rng=rng)
        config = archetype_map.get(archetype_id)

        if config is None:
            # fallback: elderly_pensioner が分割前の設定しかない場合
            if archetype_id in ("active_elderly", "late_elderly"):
                # 仮設定
                config = {
                    "id": archetype_id,
                    "name_ja": "前期高齢者" if archetype_id == "active_elderly" else "後期高齢者",
                    "age_range": [65, 74] if archetype_id == "active_elderly" else [75, 90],
                    "gender": "any",
                    "political_engagement": "high",
                    "typical_concerns": ["年金", "医療", "介護", "社会保障"],
                    "voting_behavior": {
                        "turnout_probability": 0.75 if archetype_id == "active_elderly" else 0.65,
                        "swing_tendency": "low" if archetype_id == "active_elderly" else "very_low",
                        "information_source": ["テレビ", "新聞", "地域組織"],
                    },
                }
            else:
                continue

        # 年齢
        age_min, age_max = config["age_range"]
        age = rng.randint(age_min, age_max)

        # 性別
        if config.get("gender") == "male":
            gender = "男性"
        elif config.get("gender") == "female":
            gender = "女性"
        else:
            gender = "男性" if rng.random() < GENDER_RATIO["男性"] else "女性"

        # 職業
        occupations = OCCUPATION_MAP.get(archetype_id, ["その他"])
        occupation = rng.choice(occupations)

        # 政治関心度
        engagement = config.get("political_engagement", "moderate")

        # 投票確率（天候修正付き）
        base_turnout = config["voting_behavior"]["turnout_probability"]
        turnout_prob = max(0.05, min(0.95, base_turnout + weather_region))

        # スイング傾向
        swing = config["voting_behavior"]["swing_tendency"]

        # 関心事
        concerns = config.get("typical_concerns", [])

        # 情報源
        info_sources = config["voting_behavior"].get("information_source", [])

        # 政党支持傾向（アーキタイプ×選挙区の政治傾向を組み合わせ）
        ideology_dist = IDEOLOGY_MAP.get(archetype_id, {"中道": 1.0})
        ideology = weighted_random_choice(ideology_dist, rng=rng)

        # 政党親和性（簡略化: 選挙区の支持率分布からサンプリング）
        party_affinity = weighted_random_choice(district_party_support, rng=rng)

        persona = Persona(
            persona_id=f"{district_id}_{str(i + 1).zfill(3)}",
            district_id=district_id,
            archetype_id=archetype_id,
            archetype_name_ja=config.get("name_ja", archetype_id),
            age=age,
            gender=gender,
            occupation=occupation,
            political_engagement=engagement,
            turnout_probability=round(turnout_prob, 3),
            swing_tendency=swing,
            top_concerns=concerns,
            information_sources=info_sources,
            party_affinity=party_affinity,
            ideology=ideology,
        )
        personas.append(persona)

    return personas


def _get_weather_impact(prefecture: str) -> float:
    """都道府県名から2/8大雪の影響度を返す"""
    heavy_snow = ["北海道", "青森県", "秋田県", "山形県", "新潟県", "富山県", "石川県", "福井県"]
    moderate_snow = ["岩手県", "宮城県", "福島県", "長野県", "鳥取県", "島根県"]

    if any(prefecture.startswith(p.rstrip("県都府")) for p in heavy_snow) or prefecture in heavy_snow:
        return -0.10  # 大雪地域: 投票率10%低下
    if any(prefecture.startswith(p.rstrip("県都府")) for p in moderate_snow) or prefecture in moderate_snow:
        return -0.05  # 積雪地域: 投票率5%低下
    return 0.0  # それ以外


def generate_all_personas(seed: int = 42, num_per_district: int = 100) -> dict[str, list[Persona]]:
    """全289選挙区のペルソナを生成"""
    config = load_archetype_config()
    archetypes = config["persona_archetypes"]
    districts = load_district_data()

    all_personas = {}
    for district_row in districts:
        district_id = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
        personas = generate_personas_for_district(
            district_row, archetypes, num_per_district, seed
        )
        all_personas[district_id] = personas

    return all_personas
