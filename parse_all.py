import re
import urllib.request

def download_page(pref_code):
    url = f'https://www.nikkei.com/special/election/candidates/pref/{pref_code}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req)
    return response.read().decode('utf-8')

def parse_candidates(html, pref_code, pref_name):
    results = []

    # Find district pattern based on prefecture name
    district_pattern = rf'{pref_name}(\d+)区'
    district_matches = list(re.finditer(district_pattern, html))

    if not district_matches:
        print(f"WARNING: No districts found for {pref_name} (code {pref_code})")
        return results

    for i, dm in enumerate(district_matches):
        district_num = int(dm.group(1))

        start = dm.start()
        if i + 1 < len(district_matches):
            end = district_matches[i + 1].start()
        else:
            end = len(html)

        section = html[start:end]

        name_pattern = r'class="dataName_d1h3345j">(.*?)<span class="dataAge_d10deg1q">\uFF08<!-- -->(\d+)<!-- -->\uFF09</span>'
        party_pattern = r'class="dataParty_d1otczh9">(.*?)</div>'
        status_pattern = r'class="dataGenmotoshin_d15tv06j">(.*?)</div>'
        wins_pattern = r'class="dataElectedCount_dgsga9e">(\d+)</div>'
        dual_pattern = r'class="dataChoufuku_d11vpuhe">(.*?)</div>'

        names = re.findall(name_pattern, section)
        parties = re.findall(party_pattern, section)
        statuses = re.findall(status_pattern, section)
        wins = re.findall(wins_pattern, section)
        duals_raw = re.findall(dual_pattern, section, re.DOTALL)

        duals = []
        for d in duals_raw:
            if '重複' in d:
                duals.append('true')
            else:
                duals.append('false')

        for j in range(len(names)):
            name = names[j][0].replace('\u3000', ' ').strip()
            name = re.sub(r'<.*?>', '', name).strip()
            age = names[j][1]
            party = parties[j] if j < len(parties) else '?'
            status = statuses[j] if j < len(statuses) else '?'
            win_count = wins[j] if j < len(wins) else '?'
            dual = duals[j] if j < len(duals) else '?'

            results.append({
                'pref_code': pref_code,
                'district': district_num,
                'name': name,
                'age': age,
                'party': party,
                'status': status,
                'wins': win_count,
                'dual': dual
            })

    return results

prefectures = {
    '13': '東京',
    '14': '神奈川',
    '15': '新潟',
    '16': '富山',
    '17': '石川',
    '18': '福井',
    '19': '山梨',
    '20': '長野',
    '21': '岐阜',
    '22': '静岡',
    '23': '愛知',
    '24': '三重',
}

all_results = []

for code, name in prefectures.items():
    if code == '13':
        # Already downloaded
        with open('/tmp/tokyo13.html', 'r') as f:
            html = f.read()
    else:
        print(f"Downloading {name} (pref {code})...", flush=True)
        html = download_page(code)

    candidates = parse_candidates(html, code, name)
    all_results.extend(candidates)
    print(f"  {name}: {len(candidates)} candidates found", flush=True)

print(f"\nTotal candidates: {len(all_results)}")
print("\n--- CSV OUTPUT ---")
print("prefecture_code,district_number,candidate_name,age,party,status,previous_wins,dual_candidacy")
for r in all_results:
    # Map party names
    party_map = {
        '自民': 'ldp',
        '中道': 'chudo',
        '維新': 'ishin',
        '国民': 'dpfp',
        '共産': 'jcp',
        'れ新': 'reiwa',
        '参政': 'sansei',
        '減ゆ': 'genzei',
        '保守': 'hoshuto',
        '社民': 'shamin',
        'みら': 'mirai',
        '諸': 'shoha',
        '無': 'independent',
    }

    party = party_map.get(r['party'], r['party'])

    # Map status
    status_map = {
        '前': 'incumbent',
        '元': 'former',
        '新': 'new',
    }
    status = status_map.get(r['status'], r['status'])

    print(f"{r['pref_code']},{r['district']},{r['name']},{r['age']},{party},{status},{r['wins']},{r['dual']}")
