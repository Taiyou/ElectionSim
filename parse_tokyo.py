import re

with open('/tmp/tokyo13.html', 'r') as f:
    html = f.read()

district_pattern = r'東京(\d+)区'
district_matches = list(re.finditer(district_pattern, html))

for i, dm in enumerate(district_matches):
    district_num = int(dm.group(1))
    if district_num < 19:
        continue

    start = dm.start()
    if i + 1 < len(district_matches):
        end = district_matches[i + 1].start()
    else:
        end = len(html)

    section = html[start:end]

    name_pattern = r'class="dataName_d1h3345j">(.*?)<span class="dataAge_d10deg1q">\（<!-- -->(\d+)<!-- -->\）</span>'
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

        print(f"{district_num}|{name}|{age}|{party}|{status}|{win_count}|{dual}")
