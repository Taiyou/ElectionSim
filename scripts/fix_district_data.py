"""
選挙区別データの個別化スクリプト

問題: all_districts_persona_data.csv で同一県内の全選挙区が完全同一データ
修正: 対象地域から都市化レベルを判定し、人口按分、年齢分布・ペルソナ分布を変調
"""

import csv
import json
import re
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PERSONA_DIR = BASE_DIR / "persona_data"
DISTRICTS_DIR = PERSONA_DIR / "districts"

# 都市化レベル判定用キーワード
# 政令指定都市の区名パターン
SEIREI_CITIES = [
    "札幌市", "仙台市", "さいたま市", "千葉市", "横浜市", "川崎市", "相模原市",
    "新潟市", "静岡市", "浜松市", "名古屋市", "京都市", "大阪市", "堺市",
    "神戸市", "岡山市", "広島市", "北九州市", "福岡市", "熊本市",
]

# 中核市リスト（主要なもの）
CORE_CITIES = [
    "旭川市", "函館市", "青森市", "盛岡市", "秋田市", "山形市", "郡山市",
    "いわき市", "宇都宮市", "前橋市", "高崎市", "川越市", "越谷市", "船橋市",
    "柏市", "八王子市", "町田市", "横須賀市", "藤沢市", "富山市", "金沢市",
    "長野市", "松本市", "岐阜市", "豊橋市", "岡崎市", "豊田市", "一宮市",
    "大津市", "高槻市", "東大阪市", "豊中市", "枚方市", "吹田市",
    "姫路市", "西宮市", "尼崎市", "明石市", "奈良市", "和歌山市",
    "倉敷市", "福山市", "呉市", "高松市", "松山市", "高知市",
    "久留米市", "長崎市", "佐世保市", "大分市", "宮崎市", "鹿児島市", "那覇市",
]

# 東京23区の区名
TOKYO_WARDS = [
    "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区",
    "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区",
    "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区",
    "葛飾区", "江戸川区",
]

# 農村・一次産業が主な地域を示すキーワード
RURAL_KEYWORDS = [
    "郡部", "島", "村", "農村", "山間", "漁村",
    "十勝", "根室", "釧路", "紋別", "留萌", "稚内",
    "五島", "壱岐", "対馬", "奄美", "宮古", "石垣",
]

# 都市化レベルの定義
URBAN_LEVELS = {
    "大都市中心": 1.0,   # 政令市中心区・東京23区中心
    "大都市": 0.85,       # 政令市・東京23区周辺
    "中核市": 0.65,       # 中核市
    "地方都市": 0.45,     # その他市
    "農村部": 0.25,       # 農村・山間・離島
}


def classify_urbanization(area_desc: str, prefecture: str) -> str:
    """対象地域テキストから都市化レベルを分類"""
    if not area_desc:
        return "地方都市"

    # 東京23区の中心部チェック
    central_tokyo_wards = ["千代田区", "中央区", "港区", "新宿区", "渋谷区", "目黒区", "品川区"]
    for ward in central_tokyo_wards:
        if ward in area_desc:
            return "大都市中心"

    # 東京23区（中心以外）
    for ward in TOKYO_WARDS:
        if ward in area_desc:
            return "大都市"

    # 政令指定都市の中心区チェック
    for city in SEIREI_CITIES:
        if city in area_desc:
            # 中心区かどうか
            if any(k in area_desc for k in ["中央区", "中区", "北区", "西区"]):
                return "大都市中心"
            return "大都市"

    # 中核市チェック
    for city in CORE_CITIES:
        if city in area_desc:
            return "中核市"

    # 農村部チェック
    for kw in RURAL_KEYWORDS:
        if kw in area_desc:
            return "農村部"

    # 「市」が含まれれば地方都市
    if "市" in area_desc:
        return "地方都市"

    # その他は地方都市
    return "地方都市"


# 都市化レベル別の年齢分布調整係数
AGE_ADJUSTMENTS = {
    "大都市中心": {
        "年齢_18〜29歳": +0.05, "年齢_30〜39歳": +0.04, "年齢_40〜49歳": +0.02,
        "年齢_50〜59歳": -0.01, "年齢_60〜69歳": -0.03, "年齢_70歳以上": -0.07,
    },
    "大都市": {
        "年齢_18〜29歳": +0.03, "年齢_30〜39歳": +0.03, "年齢_40〜49歳": +0.01,
        "年齢_50〜59歳": 0.00, "年齢_60〜69歳": -0.02, "年齢_70歳以上": -0.05,
    },
    "中核市": {
        "年齢_18〜29歳": +0.01, "年齢_30〜39歳": +0.01, "年齢_40〜49歳": 0.00,
        "年齢_50〜59歳": 0.00, "年齢_60〜69歳": -0.01, "年齢_70歳以上": -0.01,
    },
    "地方都市": {
        "年齢_18〜29歳": -0.02, "年齢_30〜39歳": -0.01, "年齢_40〜49歳": 0.00,
        "年齢_50〜59歳": 0.00, "年齢_60〜69歳": +0.01, "年齢_70歳以上": +0.02,
    },
    "農村部": {
        "年齢_18〜29歳": -0.04, "年齢_30〜39歳": -0.03, "年齢_40〜49歳": -0.01,
        "年齢_50〜59歳": +0.01, "年齢_60〜69歳": +0.03, "年齢_70歳以上": +0.04,
    },
}

# 都市化レベル別のペルソナ分布調整係数
PERSONA_ADJUSTMENTS = {
    "大都市中心": {
        "ペルソナ_都市部若年勤労者": +0.08, "ペルソナ_郊外子育て世帯": -0.02,
        "ペルソナ_中高年会社員": +0.03, "ペルソナ_中高年女性労働者": +0.02,
        "ペルソナ_農村部農業従事者": -0.06, "ペルソナ_高齢年金受給者": -0.06,
        "ペルソナ_自営業者": +0.02, "ペルソナ_公務員": +0.01,
        "ペルソナ_大学生": +0.04, "ペルソナ_専業主婦主夫": -0.02,
        "ペルソナ_非正規雇用": +0.02, "ペルソナ_労働組合員": -0.01,
    },
    "大都市": {
        "ペルソナ_都市部若年勤労者": +0.05, "ペルソナ_郊外子育て世帯": +0.02,
        "ペルソナ_中高年会社員": +0.02, "ペルソナ_中高年女性労働者": +0.01,
        "ペルソナ_農村部農業従事者": -0.05, "ペルソナ_高齢年金受給者": -0.04,
        "ペルソナ_自営業者": +0.01, "ペルソナ_公務員": 0.00,
        "ペルソナ_大学生": +0.02, "ペルソナ_専業主婦主夫": -0.01,
        "ペルソナ_非正規雇用": +0.01, "ペルソナ_労働組合員": 0.00,
    },
    "中核市": {
        "ペルソナ_都市部若年勤労者": +0.02, "ペルソナ_郊外子育て世帯": +0.01,
        "ペルソナ_中高年会社員": 0.00, "ペルソナ_中高年女性労働者": 0.00,
        "ペルソナ_農村部農業従事者": -0.02, "ペルソナ_高齢年金受給者": -0.01,
        "ペルソナ_自営業者": 0.00, "ペルソナ_公務員": +0.01,
        "ペルソナ_大学生": +0.01, "ペルソナ_専業主婦主夫": 0.00,
        "ペルソナ_非正規雇用": 0.00, "ペルソナ_労働組合員": 0.00,
    },
    "地方都市": {
        "ペルソナ_都市部若年勤労者": -0.03, "ペルソナ_郊外子育て世帯": 0.00,
        "ペルソナ_中高年会社員": -0.01, "ペルソナ_中高年女性労働者": 0.00,
        "ペルソナ_農村部農業従事者": +0.02, "ペルソナ_高齢年金受給者": +0.02,
        "ペルソナ_自営業者": +0.01, "ペルソナ_公務員": +0.01,
        "ペルソナ_大学生": -0.01, "ペルソナ_専業主婦主夫": +0.01,
        "ペルソナ_非正規雇用": -0.01, "ペルソナ_労働組合員": 0.00,
    },
    "農村部": {
        "ペルソナ_都市部若年勤労者": -0.06, "ペルソナ_郊外子育て世帯": -0.03,
        "ペルソナ_中高年会社員": -0.03, "ペルソナ_中高年女性労働者": -0.01,
        "ペルソナ_農村部農業従事者": +0.07, "ペルソナ_高齢年金受給者": +0.06,
        "ペルソナ_自営業者": +0.02, "ペルソナ_公務員": +0.01,
        "ペルソナ_大学生": -0.02, "ペルソナ_専業主婦主夫": +0.01,
        "ペルソナ_非正規雇用": -0.02, "ペルソナ_労働組合員": -0.01,
    },
}

# 都市化レベル別の社会経済調整
SOCIOECONOMIC_ADJUSTMENTS = {
    "大都市中心": {
        "都市化率": 0.98, "第一次産業比率": 0.00, "第二次産業比率": -0.05, "第三次産業比率": +0.05,
        "所得水準": "高", "年収乗数": 1.25, "失業率加算": -0.005, "大卒率加算": +0.15,
    },
    "大都市": {
        "都市化率": 0.92, "第一次産業比率": 0.00, "第二次産業比率": -0.02, "第三次産業比率": +0.02,
        "所得水準": "高", "年収乗数": 1.10, "失業率加算": -0.003, "大卒率加算": +0.08,
    },
    "中核市": {
        "都市化率": 0.75, "第一次産業比率": +0.01, "第二次産業比率": 0.00, "第三次産業比率": -0.01,
        "所得水準": "中", "年収乗数": 1.0, "失業率加算": 0.00, "大卒率加算": 0.00,
    },
    "地方都市": {
        "都市化率": 0.55, "第一次産業比率": +0.04, "第二次産業比率": +0.02, "第三次産業比率": -0.06,
        "所得水準": "中", "年収乗数": 0.90, "失業率加算": +0.005, "大卒率加算": -0.05,
    },
    "農村部": {
        "都市化率": 0.30, "第一次産業比率": +0.10, "第二次産業比率": +0.03, "第三次産業比率": -0.13,
        "所得水準": "低", "年収乗数": 0.80, "失業率加算": +0.008, "大卒率加算": -0.10,
    },
}

# 都市化レベル別の政治傾向調整
POLITICAL_ADJUSTMENTS = {
    "大都市中心": {
        "支持率_自民党": -0.05, "支持率_立憲民主党": +0.03, "支持率_維新": +0.02,
        "支持率_共産党": +0.02, "浮動票率": +0.08,
        "イデオロギー_保守": -0.05, "イデオロギー_革新": +0.05,
    },
    "大都市": {
        "支持率_自民党": -0.03, "支持率_立憲民主党": +0.02, "支持率_維新": +0.01,
        "支持率_共産党": +0.01, "浮動票率": +0.05,
        "イデオロギー_保守": -0.03, "イデオロギー_革新": +0.03,
    },
    "中核市": {
        "支持率_自民党": 0.00, "支持率_立憲民主党": 0.00, "支持率_維新": 0.00,
        "支持率_共産党": 0.00, "浮動票率": 0.00,
        "イデオロギー_保守": 0.00, "イデオロギー_革新": 0.00,
    },
    "地方都市": {
        "支持率_自民党": +0.03, "支持率_立憲民主党": -0.01, "支持率_維新": -0.01,
        "支持率_共産党": -0.01, "浮動票率": -0.03,
        "イデオロギー_保守": +0.03, "イデオロギー_革新": -0.03,
    },
    "農村部": {
        "支持率_自民党": +0.08, "支持率_立憲民主党": -0.03, "支持率_維新": -0.03,
        "支持率_共産党": -0.02, "浮動票率": -0.08,
        "イデオロギー_保守": +0.08, "イデオロギー_革新": -0.08,
    },
}


def normalize_distribution(values: dict, keys: list[str]) -> dict:
    """分布の合計を1.0に正規化（負の値は0にクランプ）"""
    for k in keys:
        if k in values:
            values[k] = max(0.0, float(values[k]))

    total = sum(float(values.get(k, 0)) for k in keys)
    if total > 0:
        for k in keys:
            if k in values:
                values[k] = round(float(values[k]) / total, 4)
    return values


def estimate_district_population(pref_population: int, pref_voters: int,
                                 num_districts: int, urban_level: str) -> tuple[int, int]:
    """選挙区別の人口・有権者数を推定（都市化レベルに基づく加重按分）"""
    weight_map = {
        "大都市中心": 1.15,
        "大都市": 1.10,
        "中核市": 1.0,
        "地方都市": 0.90,
        "農村部": 0.80,
    }
    base_pop = pref_population / num_districts
    base_voters = pref_voters / num_districts
    weight = weight_map.get(urban_level, 1.0)
    return int(base_pop * weight), int(base_voters * weight)


def process_districts():
    """メイン処理: CSVを読み込み、選挙区ごとにデータを個別化"""
    input_path = DISTRICTS_DIR / "all_districts_persona_data.csv"

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # 県ごとの選挙区数をカウント
    pref_district_counts = {}
    for row in rows:
        pref = row["都道府県"]
        pref_district_counts[pref] = pref_district_counts.get(pref, 0) + 1

    age_cols = ["年齢_18〜29歳", "年齢_30〜39歳", "年齢_40〜49歳",
                "年齢_50〜59歳", "年齢_60〜69歳", "年齢_70歳以上"]

    persona_cols = [
        "ペルソナ_都市部若年勤労者", "ペルソナ_郊外子育て世帯",
        "ペルソナ_中高年会社員", "ペルソナ_中高年女性労働者",
        "ペルソナ_農村部農業従事者", "ペルソナ_高齢年金受給者",
        "ペルソナ_自営業者", "ペルソナ_公務員",
        "ペルソナ_大学生", "ペルソナ_専業主婦主夫",
        "ペルソナ_非正規雇用", "ペルソナ_労働組合員",
    ]

    party_support_cols = [
        "支持率_自民党", "支持率_立憲民主党", "支持率_維新",
        "支持率_国民民主党", "支持率_共産党", "支持率_れいわ",
        "支持率_参政党", "支持率_その他",
    ]

    ideology_cols = ["イデオロギー_保守", "イデオロギー_中道", "イデオロギー_革新"]

    updated_rows = []
    stats = {"大都市中心": 0, "大都市": 0, "中核市": 0, "地方都市": 0, "農村部": 0}

    for row in rows:
        area_desc = row.get("対象地域", "")
        prefecture = row.get("都道府県", "")
        num_districts = pref_district_counts.get(prefecture, 1)

        # 1. 都市化レベル判定
        urban_level = classify_urbanization(area_desc, prefecture)
        stats[urban_level] += 1

        # 2. 都市化分類を更新
        urban_class_map = {
            "大都市中心": "大都市", "大都市": "大都市",
            "中核市": "中核市", "地方都市": "地方都市", "農村部": "農村部",
        }
        row["都市化分類"] = urban_class_map[urban_level]

        # 3. 人口・有権者数を按分
        pref_pop = int(row.get("総人口", 0))
        pref_voters = int(row.get("有権者数", 0))
        dist_pop, dist_voters = estimate_district_population(
            pref_pop, pref_voters, num_districts, urban_level
        )
        row["総人口"] = str(dist_pop)
        row["有権者数"] = str(dist_voters)

        # 4. 年齢分布を調整
        age_adj = AGE_ADJUSTMENTS.get(urban_level, {})
        for col in age_cols:
            base_val = float(row.get(col, 0))
            adj = age_adj.get(col, 0)
            row[col] = str(round(base_val + adj, 4))
        row = {**row, **normalize_distribution(dict(row), age_cols)}

        # 5. ペルソナ分布を調整
        persona_adj = PERSONA_ADJUSTMENTS.get(urban_level, {})
        for col in persona_cols:
            base_val = float(row.get(col, 0))
            adj = persona_adj.get(col, 0)
            row[col] = str(round(base_val + adj, 4))
        row = {**row, **normalize_distribution(dict(row), persona_cols)}

        # 6. 社会経済指標を調整
        socio_adj = SOCIOECONOMIC_ADJUSTMENTS.get(urban_level, {})
        if "都市化率" in socio_adj:
            row["都市化率"] = str(socio_adj["都市化率"])
        for col in ["第一次産業比率", "第二次産業比率", "第三次産業比率"]:
            base_val = float(row.get(col, 0))
            adj = socio_adj.get(col, 0)
            row[col] = str(round(max(0, base_val + adj), 4))
        # 産業比率正規化
        row = {**row, **normalize_distribution(dict(row), ["第一次産業比率", "第二次産業比率", "第三次産業比率"])}

        if "所得水準" in socio_adj:
            row["所得水準"] = socio_adj["所得水準"]
        if "年収乗数" in socio_adj:
            base_income = float(row.get("平均年収（円）", 0))
            row["平均年収（円）"] = str(int(base_income * socio_adj["年収乗数"]))
        if "失業率加算" in socio_adj:
            base_rate = float(row.get("失業率", 0))
            row["失業率"] = str(round(max(0.01, base_rate + socio_adj["失業率加算"]), 4))
        if "大卒率加算" in socio_adj:
            base_rate = float(row.get("大卒率", 0))
            row["大卒率"] = str(round(max(0.1, min(0.8, base_rate + socio_adj["大卒率加算"])), 4))

        # 7. 政治傾向を調整
        pol_adj = POLITICAL_ADJUSTMENTS.get(urban_level, {})
        for col in party_support_cols:
            if col in pol_adj:
                base_val = float(row.get(col, 0))
                row[col] = str(round(base_val + pol_adj[col], 4))
        row = {**row, **normalize_distribution(dict(row), party_support_cols)}

        for col in ideology_cols:
            if col in pol_adj:
                base_val = float(row.get(col, 0))
                row[col] = str(round(base_val + pol_adj[col], 4))
        row = {**row, **normalize_distribution(dict(row), ideology_cols)}

        if "浮動票率" in pol_adj:
            base_val = float(row.get("浮動票率", 0))
            row["浮動票率"] = str(round(max(0.1, min(0.6, base_val + pol_adj["浮動票率"])), 4))

        # 8. 高齢化依存率を年齢分布に基づいて再計算
        age_70_ratio = float(row.get("年齢_70歳以上", 0.25))
        age_60_ratio = float(row.get("年齢_60〜69歳", 0.15))
        row["高齢化依存率"] = str(round(age_70_ratio + age_60_ratio * 0.3, 4))

        updated_rows.append(row)

    # 出力
    output_path = DISTRICTS_DIR / "all_districts_persona_data.csv"
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"処理完了: {len(updated_rows)} 選挙区")
    print(f"都市化レベル分布: {stats}")

    # 検証: 同一県内で差異があることを確認
    verify_differentiation(updated_rows)


def verify_differentiation(rows: list[dict]):
    """同一県内でデータに差異があることを検証"""
    from collections import defaultdict
    by_pref = defaultdict(list)
    for row in rows:
        by_pref[row["都道府県"]].append(row)

    print("\n=== 検証結果 ===")
    differentiated = 0
    total_multi = 0
    for pref, districts in sorted(by_pref.items()):
        if len(districts) <= 1:
            continue
        total_multi += 1

        # 都市化分類が全て同じかチェック
        urban_classes = set(d.get("都市化分類", "") for d in districts)
        pop_values = set(d.get("総人口", "") for d in districts)

        if len(urban_classes) > 1 or len(pop_values) > 1:
            differentiated += 1
            print(f"  {pref} ({len(districts)}区): 都市化={urban_classes}, "
                  f"人口={len(pop_values)}パターン")
        else:
            print(f"  {pref} ({len(districts)}区): 未分化（全区同一都市化レベル）")

    print(f"\n分化済み: {differentiated}/{total_multi} 都道府県")


if __name__ == "__main__":
    process_districts()
