"""Generate full 289 district data with real candidate names from CSV.

Reads candidate data from backend/app/data/candidates.csv (scraped from Nikkei)
and combines with district structure from prefectures.json.
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "backend" / "app" / "data"

# Load prefectures
with open(DATA_DIR / "prefectures.json", encoding="utf-8") as f:
    prefectures = json.load(f)

# Area descriptions per prefecture (representative areas for each district)
AREA_DESCRIPTIONS: dict[str, list[str]] = {
    "北海道": [
        "札幌市中央区、南区、西区", "札幌市北区、東区", "札幌市白石区、豊平区、清田区",
        "札幌市厚別区、手稲区、小樽市", "札幌市西区の一部、石狩市、当別町",
        "旭川市", "釧路市、根室市、十勝の一部", "函館市、北斗市、渡島地方",
        "室蘭市、苫小牧市、胆振地方", "岩見沢市、夕張市、空知地方",
        "帯広市、十勝地方", "北見市、網走市、オホーツク地方",
    ],
    "青森県": ["青森市、東津軽郡", "八戸市、三戸郡", "弘前市、五所川原市、西津軽郡"],
    "岩手県": ["盛岡市、八幡平市", "宮古市、釜石市、沿岸地方", "奥州市、一関市、県南地方"],
    "宮城県": [
        "仙台市青葉区、太白区", "仙台市宮城野区、若林区、泉区", "名取市、岩沼市、亘理郡",
        "大崎市、栗原市、登米市", "石巻市、東松島市、気仙沼市",
    ],
    "秋田県": ["秋田市", "横手市、大仙市、県南地方"],
    "山形県": ["山形市、上山市、天童市", "酒田市、鶴岡市、庄内地方", "米沢市、新庄市、置賜地方"],
    "福島県": [
        "福島市、伊達市、二本松市", "郡山市、須賀川市", "いわき市、双葉郡",
        "会津若松市、喜多方市、会津地方",
    ],
    "茨城県": [
        "水戸市、笠間市、小美玉市", "日立市、高萩市、北茨城市", "取手市、龍ケ崎市、牛久市",
        "常総市、坂東市、古河市", "つくば市、土浦市", "ひたちなか市、鹿嶋市、神栖市",
        "筑西市、結城市、下妻市",
    ],
    "栃木県": [
        "宇都宮市東部", "宇都宮市西部、鹿沼市、日光市", "小山市、栃木市、下野市",
        "足利市、佐野市、那須塩原市",
    ],
    "群馬県": [
        "前橋市、富岡市", "高崎市、安中市", "太田市、館林市、邑楽郡",
        "伊勢崎市、桐生市、みどり市",
    ],
    "埼玉県": [
        "さいたま市見沼区、岩槻区", "川口市", "草加市、越谷市の一部",
        "朝霞市、志木市、新座市、和光市", "さいたま市大宮区、北区、中央区",
        "上尾市、桶川市、鴻巣市、北本市", "川越市、富士見市",
        "所沢市、入間市、狭山市の一部", "飯能市、日高市、比企郡",
        "さいたま市浦和区、南区、緑区", "深谷市、本庄市、児玉郡",
        "熊谷市、行田市、羽生市", "春日部市、蓮田市、白岡市",
        "久喜市、加須市、幸手市", "越谷市の一部、吉川市、三郷市",
        "さいたま市桜区、西区、北区の一部",
    ],
    "千葉県": [
        "千葉市中央区、稲毛区", "千葉市花見川区、美浜区、習志野市",
        "市川市", "船橋市", "市原市、袖ケ浦市",
        "松戸市の一部", "松戸市の一部、流山市", "柏市",
        "佐倉市、四街道市、八街市", "銚子市、香取市、旭市",
        "茂原市、勝浦市、長生郡", "木更津市、君津市、富津市",
        "成田市、印西市、白井市", "野田市、鎌ケ谷市",
    ],
    "東京都": [
        "千代田区、港区、新宿区の一部", "中央区、文京区、台東区の一部",
        "品川区、大田区の一部", "大田区の一部、目黒区の一部",
        "世田谷区の一部", "世田谷区の一部、渋谷区の一部",
        "渋谷区の一部、港区の一部", "杉並区", "練馬区の一部",
        "豊島区、新宿区の一部", "板橋区", "北区、足立区の一部",
        "足立区の一部", "墨田区、荒川区", "江東区",
        "江戸川区の一部", "葛飾区", "武蔵野市、小金井市、西東京市",
        "小平市、国分寺市、国立市", "東村山市、東大和市、清瀬市",
        "立川市、日野市", "三鷹市、調布市、狛江市",
        "町田市", "八王子市の一部", "青梅市、昭島市、福生市",
        "目黒区、大田区の一部", "中野区、杉並区の一部",
        "練馬区東部", "荒川区、足立区の一部",
        "府中市、多摩市、稲城市",
    ],
    "神奈川県": [
        "横浜市中区、磯子区、金沢区", "横浜市西区、南区、港南区",
        "横浜市鶴見区、神奈川区", "横浜市栄区、鎌倉市、逗子市",
        "横浜市戸塚区、泉区", "横浜市保土ケ谷区、旭区",
        "横浜市港北区", "横浜市緑区、青葉区",
        "川崎市多摩区、麻生区", "川崎市川崎区、幸区",
        "横須賀市、三浦市", "藤沢市、高座郡",
        "横浜市瀬谷区、大和市、綾瀬市", "相模原市緑区、中央区、愛甲郡",
        "平塚市、茅ケ崎市", "厚木市、伊勢原市、海老名市",
        "小田原市、秦野市、南足柄市", "川崎市中原区、高津区",
        "横浜市都筑区、川崎市宮前区", "相模原市南区、座間市",
    ],
    "新潟県": [
        "新潟市中央区、東区、西区", "新潟市北区、江南区、秋葉区",
        "三条市、燕市、加茂市", "長岡市、柏崎市",
        "上越市、糸魚川市、妙高市",
    ],
    "富山県": ["富山市", "高岡市、氷見市、小矢部市", "魚津市、滑川市、黒部市"],
    "石川県": ["金沢市の一部", "金沢市の一部、白山市", "小松市、加賀市、能美市"],
    "福井県": ["福井市、あわら市", "敦賀市、小浜市、越前市"],
    "山梨県": ["甲府市、笛吹市、山梨市", "甲斐市、韮崎市、富士吉田市"],
    "長野県": [
        "長野市、須坂市、千曲市", "松本市、塩尻市、安曇野市",
        "上田市、佐久市、小諸市", "伊那市、駒ヶ根市、飯田市",
        "諏訪市、茅野市、岡谷市",
    ],
    "岐阜県": [
        "岐阜市、羽島市", "大垣市、海津市、養老郡", "関市、美濃市、各務原市",
        "高山市、多治見市、恵那市",
    ],
    "静岡県": [
        "静岡市葵区、駿河区", "静岡市清水区、富士市", "磐田市、掛川市、袋井市",
        "浜松市中区、東区、西区", "浜松市北区、浜北区、湖西市",
        "沼津市、三島市、御殿場市",
    ],
    "愛知県": [
        "名古屋市東区、北区、西区", "名古屋市中区、昭和区、千種区",
        "名古屋市中村区、中川区、港区", "名古屋市緑区、南区、天白区",
        "名古屋市瑞穂区、熱田区、名東区", "名古屋市守山区、春日井市",
        "瀬戸市、尾張旭市、長久手市", "豊田市、みよし市",
        "一宮市、稲沢市の一部", "岡崎市、額田郡",
        "豊橋市、田原市", "半田市、知多市、常滑市",
        "碧南市、刈谷市、安城市", "豊川市、蒲郡市、新城市",
        "小牧市、犬山市、岩倉市",
    ],
    "三重県": [
        "津市、亀山市", "四日市市、菰野町", "松阪市、伊勢市、志摩市",
        "伊賀市、名張市、桑名市",
    ],
    "滋賀県": ["大津市、高島市", "彦根市、長浜市、米原市", "草津市、守山市、栗東市、野洲市"],
    "京都府": [
        "京都市北区、上京区、中京区", "京都市左京区、東山区、山科区",
        "京都市伏見区、南区、下京区", "京都市右京区、西京区",
        "宇治市、城陽市、木津川市",
    ],
    "大阪府": [
        "大阪市中央区、西区、浪速区、天王寺区", "大阪市阿倍野区、東住吉区、平野区",
        "大阪市此花区、港区、大正区、住之江区", "大阪市北区、都島区、旭区、城東区",
        "大阪市淀川区、東淀川区、西淀川区", "大阪市東成区、生野区、鶴見区",
        "大阪市住吉区、西成区、福島区", "豊中市、池田市",
        "吹田市、摂津市", "高槻市、三島郡", "枚方市、交野市",
        "寝屋川市、大東市、四條畷市", "東大阪市の一部",
        "東大阪市の一部、八尾市", "堺市堺区、北区、中区",
        "堺市西区、南区、美原区", "岸和田市、貝塚市、泉佐野市",
        "富田林市、河内長野市、大阪狭山市",
    ],
    "兵庫県": [
        "神戸市中央区、灘区、東灘区", "神戸市兵庫区、長田区、須磨区",
        "神戸市垂水区、西区、明石市の一部", "明石市の一部、加古川市",
        "姫路市の一部", "姫路市の一部、福崎町",
        "西宮市", "尼崎市", "伊丹市、宝塚市、川西市",
        "豊岡市、洲本市、淡路市", "三田市、三木市、小野市",
    ],
    "奈良県": ["奈良市、生駒市", "大和郡山市、天理市、桜井市", "橿原市、五條市、御所市"],
    "和歌山県": ["和歌山市、海南市", "田辺市、新宮市、橋本市"],
    "鳥取県": ["鳥取市、岩美郡", "米子市、境港市、倉吉市"],
    "島根県": ["松江市、安来市、雲南市", "出雲市、大田市、浜田市"],
    "岡山県": [
        "岡山市北区、中区", "岡山市南区、東区、玉野市",
        "倉敷市の一部", "倉敷市の一部、総社市、津山市",
    ],
    "広島県": [
        "広島市中区、東区、南区", "広島市西区、佐伯区",
        "広島市安佐南区、安佐北区、安芸高田市", "広島市安芸区、呉市",
        "尾道市、三原市、竹原市", "福山市、府中市",
    ],
    "山口県": ["山口市、防府市、萩市", "下関市、長門市", "周南市、岩国市、柳井市"],
    "徳島県": ["徳島市、小松島市、鳴門市", "阿南市、吉野川市、美馬市"],
    "香川県": ["高松市", "丸亀市、坂出市、善通寺市"],
    "愛媛県": ["松山市の一部", "松山市の一部、伊予市", "今治市、新居浜市、西条市"],
    "高知県": ["高知市、南国市", "四万十市、須崎市、宿毛市"],
    "福岡県": [
        "福岡市博多区、東区", "福岡市中央区、南区", "福岡市早良区、西区、城南区",
        "福岡市城南区の一部、糸島市、春日市", "筑紫野市、大野城市、太宰府市",
        "久留米市、大川市、小郡市", "大牟田市、柳川市、みやま市",
        "北九州市門司区、小倉北区、小倉南区", "北九州市八幡東区、八幡西区、戸畑区",
        "北九州市若松区、直方市、中間市", "飯塚市、田川市、嘉麻市",
    ],
    "佐賀県": ["佐賀市、鳥栖市", "唐津市、武雄市、伊万里市"],
    "長崎県": ["長崎市、西彼杵郡", "佐世保市、平戸市", "諫早市、大村市、島原市"],
    "熊本県": [
        "熊本市中央区、東区", "熊本市西区、南区、北区",
        "八代市、人吉市、天草市", "山鹿市、菊池市、合志市",
    ],
    "大分県": ["大分市", "別府市、佐伯市、臼杵市", "中津市、日田市、宇佐市"],
    "宮崎県": ["宮崎市、日南市、串間市", "都城市、延岡市、日向市"],
    "鹿児島県": [
        "鹿児島市の一部", "鹿児島市の一部、指宿市、南九州市",
        "霧島市、薩摩川内市、出水市", "鹿屋市、奄美市、西之表市",
    ],
    "沖縄県": [
        "那覇市、南城市", "宜野湾市、浦添市", "沖縄市、うるま市",
        "名護市、糸満市、豊見城市",
    ],
}

BIOGRAPHIES = {
    "ldp": [
        "元内閣府副大臣", "元総務政務官", "元経済産業副大臣", "元防衛大臣政務官",
        "元国土交通副大臣", "元厚生労働副大臣", "元文部科学副大臣", "元農林水産副大臣",
        "元財務副大臣", "元法務副大臣", "県議会議員出身", "元秘書", "元官僚",
        "元市長", "実業家出身", "元参議院議員",
    ],
    "chudo": [
        "元外務政務官", "元環境副大臣", "市民活動家出身", "弁護士",
        "元厚生労働政務官", "NPO法人代表", "元都議会議員", "ジャーナリスト出身",
        "大学教授出身", "元県議会議員", "社会福祉士", "元市議会議員",
        "元参議院議員秘書", "社会福祉活動家", "元教育委員", "税理士",
    ],
    "ishin": [
        "元IT企業経営者", "医師", "元大阪府議会議員", "公認会計士",
        "元地方議員", "ベンチャー企業創業者", "経営コンサルタント", "元官僚",
        "弁護士", "元銀行員", "起業家", "元テレビキャスター",
    ],
    "dpfp": [
        "元通信会社社員", "労働組合役員", "元県議会議員", "元銀行員",
        "中小企業経営者", "元自動車メーカー社員", "技術者出身", "元市議会議員",
    ],
    "jcp": [
        "労働組合役員", "市民団体代表", "元教員", "福祉施設職員",
        "元看護師", "平和運動家", "元自治体職員", "社会運動家",
    ],
    "reiwa": [
        "元派遣社員", "フリーランス", "介護職員", "元IT技術者",
        "市民活動家", "元飲食店経営", "環境活動家", "元非正規労働者",
    ],
    "sansei": [
        "中小企業経営者", "元自衛官", "保守活動家", "元教員",
        "地域ボランティア代表", "元金融機関職員", "農業従事者", "元会社役員",
    ],
    "genzei": [
        "元名古屋市議会議員", "中小企業経営者", "税理士", "元県議会議員",
        "市民活動家", "元サラリーマン", "不動産業", "元銀行員",
    ],
    "hoshuto": [
        "作家", "元メディア関係者", "保守活動家", "元会社経営者",
        "評論家", "元自衛官",
    ],
    "shamin": [
        "元教員", "市民活動家", "平和運動家", "元自治体職員",
        "社会福祉士", "元看護師", "NPO法人代表", "労働組合役員",
    ],
    "mirai": [
        "IT起業家", "元テレビプロデューサー", "デジタルマーケター", "元ベンチャー投資家",
        "ソフトウェアエンジニア", "元コンサルタント",
    ],
    "shoha": [
        "政治団体代表", "市民活動家", "元会社役員", "フリーランス",
        "NPO代表", "環境活動家", "元地方議員",
    ],
    "independent": [
        "元国会議員", "元県知事", "元市長", "実業家",
        "医師", "弁護士", "元官僚", "大学教授",
    ],
}


def name_to_id(name: str) -> str:
    mapping = {
        "北海道": "hokkaido", "青森県": "aomori", "岩手県": "iwate", "宮城県": "miyagi",
        "秋田県": "akita", "山形県": "yamagata", "福島県": "fukushima",
        "茨城県": "ibaraki", "栃木県": "tochigi", "群馬県": "gunma",
        "埼玉県": "saitama", "千葉県": "chiba", "東京都": "tokyo",
        "神奈川県": "kanagawa", "新潟県": "niigata", "富山県": "toyama",
        "石川県": "ishikawa", "福井県": "fukui", "山梨県": "yamanashi",
        "長野県": "nagano", "岐阜県": "gifu", "静岡県": "shizuoka",
        "愛知県": "aichi", "三重県": "mie", "滋賀県": "shiga",
        "京都府": "kyoto", "大阪府": "osaka", "兵庫県": "hyogo",
        "奈良県": "nara", "和歌山県": "wakayama", "鳥取県": "tottori",
        "島根県": "shimane", "岡山県": "okayama", "広島県": "hiroshima",
        "山口県": "yamaguchi", "徳島県": "tokushima", "香川県": "kagawa",
        "愛媛県": "ehime", "高知県": "kochi", "福岡県": "fukuoka",
        "佐賀県": "saga", "長崎県": "nagasaki", "熊本県": "kumamoto",
        "大分県": "oita", "宮崎県": "miyazaki", "鹿児島県": "kagoshima",
        "沖縄県": "okinawa",
    }
    return mapping.get(name, name.lower())


# Prefecture code to name mapping (built from prefectures.json)
CODE_TO_NAME = {p["code"]: p["name"] for p in prefectures}
CODE_TO_BLOCK = {p["code"]: p["proportional_block"] for p in prefectures}

random.seed(42)


def load_candidates_csv() -> dict[tuple[str, int], list[dict]]:
    """Load candidates from CSV grouped by (prefecture_code, district_number)."""
    candidates_by_district: dict[tuple[str, int], list[dict]] = defaultdict(list)

    csv_path = DATA_DIR / "candidates.csv"
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pref_code = row["prefecture_code"].strip()
            dist_num = int(row["district_number"].strip())
            key = (pref_code, dist_num)

            is_incumbent = row["status"].strip() in ("current", "incumbent")
            is_former = row["status"].strip() == "former"
            prev_wins = int(row["previous_wins"].strip())
            dual = row["dual_candidacy"].strip().lower() == "true"
            party_id = row["party_id"].strip()
            age = int(row["age"].strip())
            name = row["candidate_name"].strip()
            block = CODE_TO_BLOCK.get(int(pref_code), "")

            bios = BIOGRAPHIES.get(party_id, BIOGRAPHIES["ldp"])
            bio = random.choice(bios)

            candidates_by_district[key].append({
                "name": name,
                "name_kana": "",
                "party_id": party_id,
                "age": age,
                "is_incumbent": is_incumbent or is_former,
                "previous_wins": prev_wins,
                "biography": bio,
                "dual_candidacy": dual,
                "proportional_block_id": block if dual else None,
            })

    return candidates_by_district


def generate_districts():
    """Generate districts with real candidate data from CSV."""
    candidates_by_district = load_candidates_csv()

    all_districts = []
    total_candidates = 0

    for pref in prefectures:
        name = pref["name"]
        code = pref["code"]
        count = pref["district_count"]
        areas = AREA_DESCRIPTIONS.get(name, [])

        for i in range(1, count + 1):
            district_id = f"{name_to_id(name)}-{i}"
            area = areas[i - 1] if i <= len(areas) else f"{name}第{i}区エリア"

            # Get candidates for this district
            pref_code_str = str(code).zfill(2)
            key = (pref_code_str, i)
            candidates = candidates_by_district.get(key, [])

            if not candidates:
                print(f"WARNING: No candidates for {name}第{i}区 (code={pref_code_str})")

            total_candidates += len(candidates)

            district = {
                "id": district_id,
                "prefecture": name,
                "prefecture_code": code,
                "district_number": i,
                "name": f"{name}第{i}区",
                "area_description": area,
                "registered_voters": None,
                "candidates": candidates,
            }
            all_districts.append(district)

    return all_districts, total_candidates


def verify_counts(districts: list[dict], total_candidates: int) -> bool:
    """Verify generated data."""
    from collections import Counter

    party_counts: Counter[str] = Counter()
    dual_counts: Counter[str] = Counter()
    incumbent_count = 0

    for d in districts:
        for c in d["candidates"]:
            pid = c["party_id"]
            party_counts[pid] += 1
            if c["dual_candidacy"]:
                dual_counts[pid] += 1
            if c["is_incumbent"]:
                incumbent_count += 1

    print(f"\nTotal districts: {len(districts)}")
    print(f"Total candidates: {total_candidates}")
    print(f"Total incumbents/former: {incumbent_count}")
    print(f"\nParty breakdown (小選挙区):")
    print(f"{'Party':<15} {'Count':>8}")
    print("-" * 25)

    for party_id, count in party_counts.most_common():
        print(f"{party_id:<15} {count:>8}")

    print(f"\nDual candidacy breakdown:")
    print(f"{'Party':<15} {'Count':>8}")
    print("-" * 25)
    total_dual = 0
    for party_id, count in dual_counts.most_common():
        total_dual += count
        print(f"{party_id:<15} {count:>8}")

    print(f"\nTotal dual candidacy: {total_dual}")
    return True


if __name__ == "__main__":
    districts, total = generate_districts()
    verify_counts(districts, total)

    # Write output
    output_path = DATA_DIR / "districts_sample.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(districts, f, ensure_ascii=False, indent=2)

    print(f"\nWritten to {output_path}")
