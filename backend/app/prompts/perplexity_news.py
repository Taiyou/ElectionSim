PERPLEXITY_PREFECTURE_PROMPT = """
あなたは日本の選挙分析の専門家です。
今日は {today} です。

以下の都道府県における衆議院選挙の最新情勢を分析してください。

【対象都道府県】{prefecture}

【対象選挙区と候補者】
{districts_and_candidates}

以下の情報を収集・分析してください：
1. 各選挙区に関する最新ニュース報道
2. 世論調査結果（支持率、政党支持率）
3. 地域特有の争点
4. 候補者の最近の活動・発言
5. 組織票の動向（労働組合、業界団体等）

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください：
{{
  "prefecture": "{prefecture}",
  "analysis_date": "{today}",
  "districts": [
    {{
      "district_id": "選挙区ID",
      "news_highlights": ["ニュース要約1", "ニュース要約2"],
      "poll_data": {{
        "source": "調査元",
        "date": "調査日",
        "results": "概要"
      }},
      "local_issues": ["地域争点1", "争点2"],
      "candidate_activities": [
        {{"name": "候補者名", "party": "政党", "recent_activity": "活動概要"}}
      ],
      "overall_assessment": "総合評価テキスト"
    }}
  ],
  "prefecture_trend": "都道府県全体の傾向"
}}
"""
