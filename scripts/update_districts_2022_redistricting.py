#!/usr/bin/env python3
"""
Update persona data files for 2022 redistricting:
- Remove 12 abolished districts from all_districts_persona_data.csv
- Add 12 new districts to the CSV
- Update districts_sample.json with corrected area_description for new districts
"""

import csv
import json
import copy
import os

BASE_DIR = "/Users/hirotaiyohamada/Desktop/10_その他/replication-horiemonAI"
CSV_PATH = os.path.join(BASE_DIR, "persona_data/districts/all_districts_persona_data.csv")
JSON_PATH = os.path.join(BASE_DIR, "backend/app/data/districts_sample.json")
CANDIDATES_PATH = os.path.join(BASE_DIR, "backend/app/data/candidates.csv")

# ============================================================
# Configuration
# ============================================================

# Districts to REMOVE (abolished in 2022 redistricting)
# Format: (prefecture_code, district_number)
ABOLISHED_DISTRICTS = [
    (4, 6),   # 宮城県6区
    (7, 5),   # 福島県5区
    (15, 6),  # 新潟県6区
    (24, 5),  # 三重県5区
    (25, 4),  # 滋賀県4区
    (29, 4),  # 奈良県4区
    (30, 3),  # 和歌山県3区
    (33, 5),  # 岡山県5区
    (34, 7),  # 広島県7区
    (35, 4),  # 山口県4区
    (38, 4),  # 愛媛県4区
    (43, 5),  # 熊本県5区
]

# Party ID to Japanese name mapping
PARTY_MAP = {
    'ldp': '自民党',
    'chudo': '中道改革連合',
    'jcp': '共産党',
    'dpfp': '国民民主党',
    'ishin': '日本維新の会',
    'reiwa': 'れいわ新選組',
    'sansei': '参政党',
    'independent': '無所属',
    'hoshuto': '保守党',
    'genzei': '減税日本',
    'mirai': 'みらい',
}

# Prefecture code -> name mapping (for new districts)
PREFECTURE_NAMES = {
    11: '埼玉県', 12: '千葉県', 13: '東京都',
    14: '神奈川県', 23: '愛知県', 47: '沖縄県',
}

# Prefecture code -> romanji for JSON id
PREFECTURE_ROMANJI = {
    11: 'saitama', 12: 'chiba', 13: 'tokyo',
    14: 'kanagawa', 23: 'aichi', 47: 'okinawa',
}

# Prefecture code -> proportional block id
PROPORTIONAL_BLOCKS = {
    11: 'kitakanto', 12: 'minamikanto', 13: 'tokyo',
    14: 'minamikanto', 23: 'tokai', 47: 'kyushu',
}

# New districts data
# template_district is the highest existing district in the same prefecture
NEW_DISTRICTS = [
    {
        'prefecture_code': 11, 'district_number': 16,
        'name': '埼玉県16区',
        'area': '春日部市、蓮田市、白岡市、杉戸町、宮代町',
        'candidates_count': 3,
        'parties': ['ldp', 'chudo', 'jcp'],
        'registered_voters': 373279,
        'turnout_2024': 0.4804,
        'template_district': 15,
        'urbanization': '地方都市',
    },
    {
        'prefecture_code': 12, 'district_number': 14,
        'name': '千葉県14区',
        'area': '船橋市の一部、習志野市',
        'candidates_count': 4,
        'parties': ['chudo', 'ldp', 'jcp', 'reiwa'],
        'registered_voters': 412495,
        'turnout_2024': 0.5458,
        'template_district': 13,
        'urbanization': '中核市',
    },
    {
        'prefecture_code': 13, 'district_number': 26,
        'name': '東京都26区',
        'area': '目黒区の一部、大田区の一部',
        'candidates_count': 6,
        'parties': ['jcp', 'dpfp', 'independent', 'mirai', 'ldp', 'sansei'],
        'registered_voters': 420000,
        'turnout_2024': 0.5717,
        'template_district': 25,
        'urbanization': '大都市',
    },
    {
        'prefecture_code': 13, 'district_number': 27,
        'name': '東京都27区',
        'area': '中野区、杉並区の一部',
        'candidates_count': 4,
        'parties': ['chudo', 'sansei', 'ldp', 'dpfp'],
        'registered_voters': 381714,
        'turnout_2024': 0.5561,
        'template_district': 25,
        'urbanization': '大都市',
    },
    {
        'prefecture_code': 13, 'district_number': 28,
        'name': '東京都28区',
        'area': '練馬区の一部',
        'candidates_count': 6,
        'parties': ['sansei', 'ishin', 'ldp', 'jcp', 'chudo', 'dpfp'],
        'registered_voters': 313446,
        'turnout_2024': 0.5716,
        'template_district': 25,
        'urbanization': '大都市',
    },
    {
        'prefecture_code': 13, 'district_number': 29,
        'name': '東京都29区',
        'area': '荒川区、足立区の一部',
        'candidates_count': 6,
        'parties': ['sansei', 'chudo', 'jcp', 'ldp', 'dpfp', 'hoshuto'],
        'registered_voters': 355382,
        'turnout_2024': 0.5301,
        'template_district': 25,
        'urbanization': '大都市',
    },
    {
        'prefecture_code': 13, 'district_number': 30,
        'name': '東京都30区',
        'area': '府中市、多摩市、稲城市',
        'candidates_count': 4,
        'parties': ['sansei', 'chudo', 'dpfp', 'ldp'],
        'registered_voters': 419060,
        'turnout_2024': 0.5763,
        'template_district': 25,
        'urbanization': '中核市',
    },
    {
        'prefecture_code': 14, 'district_number': 18,
        'name': '神奈川県18区',
        'area': '川崎市中原区、川崎市高津区',
        'candidates_count': 6,
        'parties': ['ldp', 'dpfp', 'chudo', 'jcp', 'sansei', 'ishin'],
        'registered_voters': 413241,
        'turnout_2024': 0.5599,
        'template_district': 17,
        'urbanization': '大都市',
    },
    {
        'prefecture_code': 14, 'district_number': 19,
        'name': '神奈川県19区',
        'area': '横浜市都筑区、川崎市宮前区',
        'candidates_count': 6,
        'parties': ['dpfp', 'sansei', 'ldp', 'ishin', 'jcp', 'independent'],
        'registered_voters': 368832,
        'turnout_2024': 0.5705,
        'template_district': 17,
        'urbanization': '大都市',
    },
    {
        'prefecture_code': 14, 'district_number': 20,
        'name': '神奈川県20区',
        'area': '相模原市南区、座間市',
        'candidates_count': 3,
        'parties': ['ishin', 'ldp', 'chudo'],
        'registered_voters': 345059,
        'turnout_2024': 0.5345,
        'template_district': 17,
        'urbanization': '中核市',
    },
    {
        'prefecture_code': 23, 'district_number': 16,
        'name': '愛知県16区',
        'area': '犬山市、江南市、小牧市、北名古屋市、豊山町、大口町、扶桑町',
        'candidates_count': 5,
        'parties': ['sansei', 'genzei', 'ldp', 'chudo', 'dpfp'],
        'registered_voters': 389051,
        'turnout_2024': 0.536,
        'template_district': 15,
        'urbanization': '地方都市',
    },
    {
        'prefecture_code': 47, 'district_number': 4,
        'name': '沖縄県4区',
        'area': '石垣市、糸満市、豊見城市、宮古島市、南城市、与那原町、南風原町、八重瀬町、多良間村、竹富町、与那国町',
        'candidates_count': 4,
        'parties': ['dpfp', 'ldp', 'chudo', 'reiwa'],
        'registered_voters': 298202,
        'turnout_2024': 0.4839,
        'template_district': 3,
        'urbanization': '地方都市',
    },
]

# ============================================================
# Part 1: Update all_districts_persona_data.csv
# ============================================================

def update_csv():
    print("=" * 60)
    print("Part 1: Updating all_districts_persona_data.csv")
    print("=" * 60)
    
    # Read existing data
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    print(f"  Read {len(rows)} rows from CSV")
    
    # Build a lookup by (prefecture_code, district_number)
    lookup = {}
    for r in rows:
        key = (int(r['都道府県コード']), int(r['区番号']))
        lookup[key] = r
    
    # Remove abolished districts
    abolished_set = set(ABOLISHED_DISTRICTS)
    removed_count = 0
    new_rows = []
    for r in rows:
        key = (int(r['都道府県コード']), int(r['区番号']))
        if key in abolished_set:
            print(f"  Removing: {r['選挙区']} ({key[0]}_{key[1]})")
            removed_count += 1
        else:
            new_rows.append(r)
    
    print(f"  Removed {removed_count} abolished districts")
    
    # Add new districts
    added_count = 0
    for nd in NEW_DISTRICTS:
        pc = nd['prefecture_code']
        dn = nd['district_number']
        template_key = (pc, nd['template_district'])
        
        if template_key not in lookup:
            print(f"  WARNING: Template district {template_key} not found!")
            continue
        
        # Clone template
        template = lookup[template_key]
        new_row = copy.deepcopy(template)
        
        # Modify specific fields
        new_row['選挙区'] = nd['name']
        new_row['区番号'] = str(dn)
        new_row['対象地域'] = nd['area']
        new_row['候補者数'] = str(nd['candidates_count'])
        
        # Convert party IDs to Japanese names
        party_names = [PARTY_MAP[p] for p in nd['parties']]
        new_row['出馬政党'] = '、'.join(party_names)
        
        # Update voter/population numbers
        new_row['有権者数'] = str(nd['registered_voters'])
        new_row['総人口'] = str(int(nd['registered_voters'] * 1.2))
        
        # Set turnout rates
        turnout_2021 = round(nd['turnout_2024'], 3)  # Use 2024 as proxy for 2021
        turnout_2017 = round(turnout_2024_to_2017(nd['turnout_2024']), 3)
        turnout_avg = round((turnout_2021 + turnout_2017) / 2, 3)
        
        new_row['投票率_2021'] = str(turnout_2021)
        new_row['投票率_2017'] = str(turnout_2017)
        new_row['投票率_平均'] = str(turnout_avg)
        
        # Update urbanization if different from template
        new_row['都市化分類'] = nd['urbanization']
        
        new_rows.append(new_row)
        added_count += 1
        print(f"  Added: {nd['name']} ({pc}_{dn}) from template {pc}_{nd['template_district']}")
    
    print(f"  Added {added_count} new districts")
    
    # Sort by prefecture_code, then district_number
    new_rows.sort(key=lambda r: (int(r['都道府県コード']), int(r['区番号'])))
    
    # Write back
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)
    
    print(f"  Written {len(new_rows)} rows to CSV")
    print(f"  Net change: {len(new_rows) - len(rows)} ({len(rows)} -> {len(new_rows)})")
    return new_rows


def turnout_2024_to_2017(turnout_2024):
    """Estimate 2017 turnout (typically slightly lower than recent)"""
    return turnout_2024 - 0.022  # ~2.2% lower


# ============================================================
# Part 2: Update districts_sample.json
# ============================================================

def update_json():
    print()
    print("=" * 60)
    print("Part 2: Updating districts_sample.json")
    print("=" * 60)
    
    # Read existing JSON
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        districts = json.load(f)
    
    print(f"  Read {len(districts)} districts from JSON")
    
    # Read candidates.csv for new district candidate data
    candidates_by_district = {}
    with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row['prefecture_code']), int(row['district_number']))
            if key not in candidates_by_district:
                candidates_by_district[key] = []
            candidates_by_district[key].append(row)
    
    # Remove abolished districts (check if any exist in JSON)
    abolished_set = set(ABOLISHED_DISTRICTS)
    removed_count = 0
    new_districts = []
    for d in districts:
        key = (d['prefecture_code'], d['district_number'])
        if key in abolished_set:
            print(f"  Removing from JSON: {d['name']} ({d['id']})")
            removed_count += 1
        else:
            new_districts.append(d)
    
    if removed_count == 0:
        print("  No abolished districts found in JSON (already removed)")
    else:
        print(f"  Removed {removed_count} abolished districts from JSON")
    
    # Correct area descriptions for new districts
    area_corrections = {
        (pc_data['prefecture_code'], pc_data['district_number']): pc_data['area']
        for pc_data in NEW_DISTRICTS
    }
    
    # Update existing new district entries with correct area_description and candidates
    updated_count = 0
    existing_new_keys = set()
    for d in new_districts:
        key = (d['prefecture_code'], d['district_number'])
        if key in area_corrections:
            existing_new_keys.add(key)
            old_area = d['area_description']
            new_area = area_corrections[key]
            if old_area != new_area:
                print(f"  Updating area for {d['id']}: '{old_area}' -> '{new_area}'")
                d['area_description'] = new_area
            
            # Update candidates from candidates.csv
            if key in candidates_by_district:
                block_id = PROPORTIONAL_BLOCKS[key[0]]
                new_candidates = []
                for c in candidates_by_district[key]:
                    is_incumbent = c['status'] in ('incumbent', 'current')
                    candidate_entry = {
                        "name": c['candidate_name'],
                        "name_kana": "",
                        "party_id": c['party_id'],
                        "age": int(c['age']),
                        "is_incumbent": is_incumbent,
                        "previous_wins": int(c['previous_wins']),
                        "biography": "",
                        "dual_candidacy": c['dual_candidacy'].lower() == 'true',
                        "proportional_block_id": block_id if c['dual_candidacy'].lower() == 'true' else None,
                    }
                    new_candidates.append(candidate_entry)
                
                # Keep existing biography if available
                old_cand_by_name = {c['name']: c for c in d.get('candidates', [])}
                for nc in new_candidates:
                    if nc['name'] in old_cand_by_name:
                        old_c = old_cand_by_name[nc['name']]
                        if old_c.get('biography'):
                            nc['biography'] = old_c['biography']
                
                d['candidates'] = new_candidates
            
            updated_count += 1
    
    # Add any new districts that don't exist yet
    added_count = 0
    for nd in NEW_DISTRICTS:
        key = (nd['prefecture_code'], nd['district_number'])
        if key not in existing_new_keys:
            # Create new entry
            pc = nd['prefecture_code']
            dn = nd['district_number']
            romanji = PREFECTURE_ROMANJI[pc]
            pref_name = PREFECTURE_NAMES[pc]
            block_id = PROPORTIONAL_BLOCKS[pc]
            
            candidates = []
            if key in candidates_by_district:
                for c in candidates_by_district[key]:
                    is_incumbent = c['status'] in ('incumbent', 'current')
                    candidate_entry = {
                        "name": c['candidate_name'],
                        "name_kana": "",
                        "party_id": c['party_id'],
                        "age": int(c['age']),
                        "is_incumbent": is_incumbent,
                        "previous_wins": int(c['previous_wins']),
                        "biography": "",
                        "dual_candidacy": c['dual_candidacy'].lower() == 'true',
                        "proportional_block_id": block_id if c['dual_candidacy'].lower() == 'true' else None,
                    }
                    candidates.append(candidate_entry)
            
            entry = {
                "id": f"{romanji}-{dn}",
                "prefecture": pref_name,
                "prefecture_code": pc,
                "district_number": dn,
                "name": f"{pref_name}第{dn}区",
                "area_description": nd['area'],
                "registered_voters": None,
                "candidates": candidates,
            }
            new_districts.append(entry)
            added_count += 1
            print(f"  Added new JSON entry: {entry['id']}")
    
    if added_count == 0:
        print("  All new districts already exist in JSON")
    else:
        print(f"  Added {added_count} new districts to JSON")
    
    print(f"  Updated {updated_count} existing new district entries")
    
    # Sort by id (which corresponds to prefecture_code then district_number order)
    new_districts.sort(key=lambda d: (d['prefecture_code'], d['district_number']))
    
    # Write back
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(new_districts, f, ensure_ascii=False, indent=2)
    
    print(f"  Written {len(new_districts)} districts to JSON")
    return new_districts


# ============================================================
# Verification
# ============================================================

def verify_csv(rows):
    print()
    print("=" * 60)
    print("Verification: CSV")
    print("=" * 60)
    
    # Check no abolished districts remain
    abolished_set = set(ABOLISHED_DISTRICTS)
    for r in rows:
        key = (int(r['都道府県コード']), int(r['区番号']))
        if key in abolished_set:
            print(f"  ERROR: Abolished district still present: {r['選挙区']}")
            return False
    print("  OK: No abolished districts remain")
    
    # Check all new districts present
    new_keys = {(nd['prefecture_code'], nd['district_number']) for nd in NEW_DISTRICTS}
    found_keys = set()
    for r in rows:
        key = (int(r['都道府県コード']), int(r['区番号']))
        if key in new_keys:
            found_keys.add(key)
    
    missing = new_keys - found_keys
    if missing:
        print(f"  ERROR: Missing new districts: {missing}")
        return False
    print("  OK: All 12 new districts present")
    
    # Check sort order
    prev_key = (0, 0)
    for r in rows:
        key = (int(r['都道府県コード']), int(r['区番号']))
        if key <= prev_key:
            print(f"  ERROR: Sort order violated at {r['選挙区']}")
            return False
        prev_key = key
    print("  OK: Sorted correctly by prefecture_code, district_number")
    
    # Check total count (should be 289 - 12 + 12 = 289)
    print(f"  Total districts: {len(rows)}")
    
    # Print new district summary
    print()
    print("  New districts added:")
    for r in rows:
        key = (int(r['都道府県コード']), int(r['区番号']))
        if key in new_keys:
            print(f"    {r['選挙区']}: 対象地域={r['対象地域']}, "
                  f"候補者数={r['候補者数']}, 有権者数={r['有権者数']}, "
                  f"投票率_平均={r['投票率_平均']}")
    
    return True


def verify_json(districts):
    print()
    print("=" * 60)
    print("Verification: JSON")
    print("=" * 60)
    
    # Check no abolished districts
    abolished_set = set(ABOLISHED_DISTRICTS)
    for d in districts:
        key = (d['prefecture_code'], d['district_number'])
        if key in abolished_set:
            print(f"  ERROR: Abolished district in JSON: {d['id']}")
            return False
    print("  OK: No abolished districts in JSON")
    
    # Check all new districts present
    new_keys = {(nd['prefecture_code'], nd['district_number']) for nd in NEW_DISTRICTS}
    found_keys = set()
    for d in districts:
        key = (d['prefecture_code'], d['district_number'])
        if key in new_keys:
            found_keys.add(key)
    
    missing = new_keys - found_keys
    if missing:
        print(f"  ERROR: Missing new districts in JSON: {missing}")
        return False
    print("  OK: All 12 new districts present in JSON")
    
    # Check sort order
    prev_key = (0, 0)
    for d in districts:
        key = (d['prefecture_code'], d['district_number'])
        if key <= prev_key:
            print(f"  ERROR: Sort order violated at {d['id']}")
            return False
        prev_key = key
    print("  OK: Sorted correctly")
    
    print(f"  Total districts in JSON: {len(districts)}")
    
    # Print new district summary
    print()
    print("  New districts in JSON:")
    for d in districts:
        key = (d['prefecture_code'], d['district_number'])
        if key in new_keys:
            cand_count = len(d.get('candidates', []))
            parties = [c['party_id'] for c in d.get('candidates', [])]
            print(f"    {d['id']}: area={d['area_description']}, "
                  f"candidates={cand_count} ({', '.join(parties)})")
    
    return True


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("Starting 2022 redistricting update...")
    print()
    
    # Part 1: CSV
    csv_rows = update_csv()
    
    # Part 2: JSON
    json_districts = update_json()
    
    # Verification
    csv_ok = verify_csv(csv_rows)
    json_ok = verify_json(json_districts)
    
    print()
    if csv_ok and json_ok:
        print("All updates completed successfully!")
    else:
        print("ERRORS detected - please review output above")
