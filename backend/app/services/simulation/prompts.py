"""
シミュレーション用バッチプロンプトテンプレート

同一選挙区の10-20ペルソナを1回のLLM呼び出しで処理する。
"""

from __future__ import annotations

# デフォルトの政治状況パラメータ
DEFAULT_POLITICAL_CLIMATE = {
    "cabinet_approval_rate": 0.65,
    "cabinet_disapproval_rate": 0.20,
    "ldp_support_rate": 0.38,
    "chudo_support_rate": 0.12,
    "ishin_support_rate": 0.08,
    "dpfp_support_rate": 0.06,
    "jcp_support_rate": 0.04,
    "no_party_rate": 0.30,
    "leader_popularity_boost": 0.05,
    "turnout_boost_from_interest": 0.02,
    "swing_voter_ldp_lean": 0.15,
}


def _build_political_context(pc: dict | None = None) -> str:
    """全国政治状況セクションを構築する（高市人気・政党支持率を反映）"""
    if pc is None:
        pc = DEFAULT_POLITICAL_CLIMATE

    cabinet_approval = round(pc.get("cabinet_approval_rate", 0.65) * 100)
    cabinet_disapproval = round(pc.get("cabinet_disapproval_rate", 0.20) * 100)
    ldp_support = round(pc.get("ldp_support_rate", 0.38) * 100)
    chudo_support = round(pc.get("chudo_support_rate", 0.12) * 100)
    ishin_support = round(pc.get("ishin_support_rate", 0.08) * 100)
    dpfp_support = round(pc.get("dpfp_support_rate", 0.06) * 100)
    jcp_support = round(pc.get("jcp_support_rate", 0.04) * 100)
    no_party = round(pc.get("no_party_rate", 0.30) * 100)
    swing_ldp_lean = round(pc.get("swing_voter_ldp_lean", 0.15) * 100)

    return f"""## 全国政治状況（2026年2月8日投開票）

### 高市内閣の状況
- 首相: 高市早苗（自民党総裁）
- 内閣支持率: {cabinet_approval}%（不支持: {cabinet_disapproval}%）
- 支持理由: 経済政策への期待、女性初の首相、外交安全保障の姿勢
- 高市首相の個人人気: 決断力・発信力への評価が高い
- 年代別傾向: 50代以上で特に支持が厚い、30-40代も経済政策で支持
- 性別傾向: 男女ともに支持が高いが、女性の「初の女性首相」への期待も

### 政党支持率（全国世論調査平均）
- 自民党: {ldp_support}%
- 中道改革連合: {chudo_support}%
- 日本維新の会: {ishin_support}%
- 国民民主党: {dpfp_support}%
- 日本共産党: {jcp_support}%
- 支持政党なし: {no_party}%

### 選挙情勢
- 与党: 自民党＋日本維新の会（連立）
- 通常国会冒頭解散、戦後最短16日間選挙
- 情勢: 自民＋維新で300議席超の勢い
- 主要争点: 消費税減税（食料品ゼロ）、物価高対策、社会保険料軽減、外交安全保障
- トランプ大統領が高市首相を支持表明
- 真冬選挙（36年ぶり）で投票率低下が懸念

### 無党派層の動向
- 高市人気により、無党派層の約{swing_ldp_lean}%が自民党候補に流れる傾向
- 「なんとなく高市さんがいい」「経済良くなりそう」といった漠然とした支持も多い
- 一方で「自民党は変わっていない」と距離を置く無党派層も存在

### 投票率への影響
- 高市首相への関心から、通常の冬選挙より投票率がやや高くなる可能性
- 特に女性や若年層の投票率にプラスの影響"""


SYSTEM_PROMPT = """あなたは日本の衆議院選挙における有権者の投票行動シミュレーターです。
与えられた複数のペルソナの属性、選挙区の候補者情報、現在の政治状況に基づいて、
各ペルソナがどのような投票行動を取るかを、最もリアルに予測してください。

重要な注意事項:
- ペルソナの年齢、職業、収入、政治関心度、支持政党傾向を総合的に考慮すること
- 高市首相の高い人気が自民党候補への投票行動に与える影響を考慮すること
  → 内閣支持率の高さは与党候補全体への追い風となる
  → 無党派層が首相の個人人気で投票先を決めるケースを反映すること
- 無党派層は「なんとなく」の判断を含め、非合理的な意思決定もリアルに反映すること
- 天候の影響を反映すること（天候予報は選挙区情報に記載）
- 高齢者は組織票の影響を受けやすい傾向がある
- 若年層はSNSやYouTubeでの情報影響が大きい傾向がある
- 前回選挙からの変化（中道改革連合の結成、自維連立等）による混乱を反映すること
- 出力は必ず指定のJSON配列形式で返すこと
- 各ペルソナの投票理由は50-150文字で具体的に記述すること"""


def build_batch_prompt(
    district_name: str,
    area_description: str,
    candidates: list[dict],
    district_context: dict,
    personas: list[dict],
    weather: str = "大雪・強烈寒波",
    political_climate: dict | None = None,
) -> str:
    """バッチプロンプトを構築する"""

    # 候補者一覧
    candidate_lines = []
    for c in candidates:
        status_map = {"incumbent": "現職", "former": "元職", "new": "新人", "current": "現職"}
        status = status_map.get(c.get("status", "new"), c.get("status", ""))
        wins = c.get("previous_wins", 0)
        party_names = {
            "ldp": "自民党", "chudo": "中道改革連合", "ishin": "日本維新の会",
            "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
            "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
            "shamin": "社民党", "mirai": "チームみらい", "independent": "無所属",
            "shoha": "諸派",
        }
        party = party_names.get(c.get("party_id", ""), c.get("party_id", ""))
        dual = "（比例重複）" if c.get("dual_candidacy") == "true" else ""
        candidate_lines.append(
            f"  - {c['candidate_name']}（{party}、{status}、当選{wins}回）{dual}"
        )

    # 政治傾向
    support_lines = []
    support_keys = [
        ("支持率_自民党", "自民"), ("支持率_立憲民主党", "中道改革連合"),
        ("支持率_維新", "維新"), ("支持率_国民民主党", "国民"),
        ("支持率_共産党", "共産"), ("支持率_れいわ", "れいわ"),
        ("支持率_参政党", "参政"), ("支持率_その他", "その他"),
    ]
    for key, label in support_keys:
        val = district_context.get(key, 0)
        pct = round(float(val) * 100, 1)
        support_lines.append(f"{label}{pct}%")

    # 地域課題
    issues = [
        district_context.get("主要課題1", ""),
        district_context.get("主要課題2", ""),
        district_context.get("主要課題3", ""),
    ]
    issues = [i for i in issues if i]

    # ペルソナ一覧
    persona_lines = []
    for idx, p in enumerate(personas, 1):
        concerns = "、".join(p.get("top_concerns", [])[:3])
        sources = "、".join(p.get("information_sources", [])[:2])
        persona_lines.append(
            f"  {idx}. [{p['archetype_name_ja']}] {p['age']}歳{p['gender']}、{p['occupation']}、"
            f"関心:{concerns}、情報源:{sources}、支持傾向:{p.get('party_affinity', '支持なし')}、"
            f"政治関心:{p.get('political_engagement', '中')}"
        )

    # 全国政治状況
    political_context = _build_political_context(political_climate)

    prompt = f"""## 選挙区情報
選挙区: {district_name}
対象地域: {area_description}
都市化分類: {district_context.get('都市化分類', '')}
天候予報: {weather}

## 候補者一覧（小選挙区）
{chr(10).join(candidate_lines)}

## 選挙区の政治傾向
政党支持率: {', '.join(support_lines)}
浮動票率: {round(float(district_context.get('浮動票率', 0.3)) * 100, 1)}%
地域課題: {', '.join(issues)}
平均投票率（過去）: {round(float(district_context.get('投票率_平均', 0.55)) * 100, 1)}%

{political_context}

## ペルソナ一覧（{len(personas)}名）
{chr(10).join(persona_lines)}

## タスク
上記{len(personas)}名のペルソナそれぞれについて、投票行動を予測してください。
以下のJSON配列形式で回答してください:

```json
[
  {{
    "persona_index": 1,
    "will_vote": true,
    "abstention_reason": null,
    "smd_vote": {{
      "candidate": "候補者名",
      "party": "政党名",
      "reason": "投票理由（50-150文字）"
    }},
    "proportional_vote": {{
      "party": "政党名",
      "reason": "投票理由（50-150文字）"
    }},
    "confidence": 0.7,
    "swing_factors": ["決め手1", "決め手2"]
  }},
  ...
]
```

注意:
- will_vote=false の場合、smd_vote と proportional_vote は null にしてください
- 棄権の場合は abstention_reason に理由を記載してください
- confidence は投票先への確信度（0.0-1.0）です"""

    return prompt


# ---------------------------------------------------------------------------
# v8a: キャリブレーション付きLLM投票プロンプト（デカップリング方式）
# ---------------------------------------------------------------------------

CALIBRATED_SYSTEM_PROMPT = """あなたは日本の衆議院選挙における有権者の投票先シミュレーターです。
与えられた複数のペルソナの属性、選挙区の候補者情報、現在の政治状況に基づいて、
各ペルソナがどの候補者に投票するかを予測してください。

重要: あなたが予測するのは「投票先の選択」のみです。
投票に行くかどうか（投票/棄権）の判断は別システムで行います。
以下のペルソナは全員投票所に来た前提で、候補者選択のみを予測してください。

注意事項:
- ペルソナの年齢、職業、収入、政治関心度、支持政党傾向を総合的に考慮すること
- 選挙区の過去の政党支持率分布を重要な参照基準として使うこと
  → 100人中の政党別得票は、過去の支持率分布から大幅に乖離しないのが通常です
  → ただし今回の選挙固有の要因（政策変更、スキャンダル等）による変動はあり得ます
- 高市首相の高い内閣支持率が自民党候補全体への追い風となることを考慮すること
  → 無党派層が首相の個人人気で自民党候補に投票するケースを反映すること
  → 高市人気は特に経済政策・外交安全保障に関心のある層に影響が大きい
- 無党派層は「なんとなく」の判断を含め、非合理的な意思決定もリアルに反映すること
  → 知名度だけで選ぶ、現職だから選ぶ、テレビで見たから選ぶ等の判断もありえる
- 高齢者は組織票・従来の投票慣性の影響を受けやすい
- 若年層はSNSやYouTubeでの情報影響が大きい
- 出力は必ず指定のJSON配列形式で返すこと
- 各ペルソナの投票理由は50-150文字で具体的に記述すること"""


def build_calibrated_batch_prompt(
    district_name: str,
    area_description: str,
    candidates: list[dict],
    district_context: dict,
    personas: list[dict],
    weather: str = "大雪・強烈寒波",
    political_climate: dict | None = None,
) -> str:
    """v8a キャリブレーション付きバッチプロンプトを構築する

    v4aとの主な違い:
    1. 投票/棄権判断を除外（ペルソナは全員投票する前提）
    2. 過去の選挙結果・支持率分布をアンカーとして明示的に提示
    3. 分布からの逸脱を抑制するガイダンスを追加
    """

    # 候補者一覧
    candidate_lines = []
    for c in candidates:
        status_map = {"incumbent": "現職", "former": "元職", "new": "新人", "current": "現職"}
        status = status_map.get(c.get("status", "new"), c.get("status", ""))
        wins = c.get("previous_wins", 0)
        party_names = {
            "ldp": "自民党", "chudo": "中道改革連合", "ishin": "日本維新の会",
            "dpfp": "国民民主党", "jcp": "日本共産党", "reiwa": "れいわ新選組",
            "sansei": "参政党", "genzei": "減税日本", "hoshuto": "日本保守党",
            "shamin": "社民党", "mirai": "チームみらい", "independent": "無所属",
        }
        party = party_names.get(c.get("party_id", ""), c.get("party_id", ""))
        dual = "（比例重複）" if c.get("dual_candidacy") == "true" else ""
        candidate_lines.append(
            f"  - {c['candidate_name']}（{party}、{status}、当選{wins}回）{dual}"
        )

    # 政治傾向（v8a: より詳細なアンカー情報）
    support_lines = []
    support_keys = [
        ("支持率_自民党", "自民"), ("支持率_立憲民主党", "中道改革連合"),
        ("支持率_維新", "維新"), ("支持率_国民民主党", "国民"),
        ("支持率_共産党", "共産"), ("支持率_れいわ", "れいわ"),
        ("支持率_参政党", "参政"), ("支持率_その他", "その他"),
    ]
    for key, label in support_keys:
        val = district_context.get(key, 0)
        pct = round(float(val) * 100, 1)
        support_lines.append(f"{label}{pct}%")

    # 地域課題
    issues = [
        district_context.get("主要課題1", ""),
        district_context.get("主要課題2", ""),
        district_context.get("主要課題3", ""),
    ]
    issues = [i for i in issues if i]

    # ペルソナ一覧
    persona_lines = []
    for idx, p in enumerate(personas, 1):
        concerns = "、".join(p.get("top_concerns", [])[:3])
        sources = "、".join(p.get("information_sources", [])[:2])

        # v10: 人口統計ペルソナの追加属性を表示
        extra = ""
        if p.get("household_type"):
            ht_map = {
                "single": "単身", "couple": "夫婦", "nuclear_family": "核家族",
                "three_generation": "三世代", "other": "その他",
            }
            extra += f"、世帯:{ht_map.get(p['household_type'], p['household_type'])}"
        if p.get("income_bracket"):
            extra += f"、所得:{p['income_bracket']}"
        if p.get("education_level"):
            extra += f"、学歴:{p['education_level']}"

        # アーキタイプベースの場合
        label = p.get("archetype_name_ja", "")
        if not label and p.get("industry_sector"):
            sector_map = {"primary": "第一次産業", "secondary": "第二次産業", "tertiary": "第三次産業"}
            label = sector_map.get(p["industry_sector"], "")

        persona_lines.append(
            f"  {idx}. [{label}] {p['age']}歳{p['gender']}、{p['occupation']}、"
            f"関心:{concerns}、情報源:{sources}、支持傾向:{p.get('party_affinity', '支持なし')}、"
            f"政治関心:{p.get('political_engagement', '中')}{extra}"
        )

    # 過去の投票率
    avg_turnout = round(float(district_context.get('投票率_平均', 0.55)) * 100, 1)
    floating_vote = round(float(district_context.get('浮動票率', 0.3)) * 100, 1)

    # 全国政治状況
    political_context = _build_political_context(political_climate)

    prompt = f"""## 選挙区情報
選挙区: {district_name}
対象地域: {area_description}
都市化分類: {district_context.get('都市化分類', '')}
天候予報: {weather}

## 候補者一覧（小選挙区）
{chr(10).join(candidate_lines)}

## 選挙区の政治傾向（重要な参照基準）
過去の政党支持率: {', '.join(support_lines)}
浮動票率: {floating_vote}%
地域課題: {', '.join(issues)}
平均投票率（過去）: {avg_turnout}%

※ 上記の支持率分布は過去のデータに基づくベースラインです。
  今回の予測はこの分布を参照しつつ、今回の選挙固有の要因を反映してください。
  通常、政党別の得票割合は過去分布から±10ポイント以内で変動します。

{political_context}

## 投票するペルソナ一覧（{len(personas)}名）
※ 以下のペルソナは全員投票所に来ています。候補者選択のみ予測してください。
{chr(10).join(persona_lines)}

## タスク
上記{len(personas)}名のペルソナそれぞれについて、投票先を予測してください。
全員が投票する前提です（will_voteは常にtrue）。

以下のJSON配列形式で回答してください:

```json
[
  {{
    "persona_index": 1,
    "will_vote": true,
    "smd_vote": {{
      "candidate": "候補者名",
      "party": "政党名",
      "reason": "投票理由（50-150文字）"
    }},
    "proportional_vote": {{
      "party": "政党名",
      "reason": "投票理由（50-150文字）"
    }},
    "confidence": 0.7,
    "swing_factors": ["決め手1", "決め手2"]
  }},
  ...
]
```"""

    return prompt
