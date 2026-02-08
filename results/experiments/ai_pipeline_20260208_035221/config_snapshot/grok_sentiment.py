GROK_SENTIMENT_PROMPT = """
あなたはX（旧Twitter）上の政治関連投稿の分析専門家です。
今日は {today} です。

以下の都道府県・選挙区について、X上の投稿を分析してください。

【対象都道府県】{prefecture}

【対象選挙区と候補者】
{districts_and_candidates}

以下を分析してください：
1. 各候補者・政党への言及量と感情（ポジティブ/ネガティブ/ニュートラル）
2. トレンドとなっている選挙関連トピック
3. 有権者の関心事項
4. 候補者のX上での活動状況
5. インフルエンサーの発言傾向

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください：
{{
  "prefecture": "{prefecture}",
  "analysis_date": "{today}",
  "districts": [
    {{
      "district_id": "選挙区ID",
      "candidate_sentiment": [
        {{
          "name": "候補者名",
          "party": "政党",
          "mention_volume": "high/medium/low",
          "sentiment": {{
            "positive": 0.0,
            "negative": 0.0,
            "neutral": 0.0
          }},
          "key_topics": ["トピック1", "トピック2"]
        }}
      ],
      "trending_topics": ["トレンド1", "トレンド2"],
      "voter_concerns": ["関心事1", "関心事2"],
      "overall_sns_mood": "SNS上の全体的な雰囲気"
    }}
  ],
  "prefecture_sns_trend": "都道府県全体のSNSトレンド"
}}
"""
