CLAUDE_INTEGRATION_PROMPT = """
あなたは日本の衆議院選挙の情勢分析を行う統合AIアナリストです。
今日は {today} です。

2つの異なるAI分析結果を統合し、各選挙区の予測を生成してください。

【対象都道府県】{prefecture}

【選挙区・候補者の基礎データ（ファクト）】
{master_data}

【ニュース・世論調査分析（情報ソース1）】
{perplexity_result}

【SNS感情分析（情報ソース2）】
{grok_result}

以下の手順で分析してください：
1. 2つの分析結果の整合性を確認し、矛盾があれば指摘
2. ニュースベースの情勢とSNSの雰囲気を総合的に判断
3. 各選挙区について、勝者予測と確信度を決定
4. 確信度は以下の基準で判定：
   - high: 情報源間で一致、明確な優位、世論調査でも差がある
   - medium: 概ね一致するが不確定要素あり
   - low: 情報源間で矛盾、接戦、流動的な情勢

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください：
{{
  "prefecture": "{prefecture}",
  "prediction_date": "{today}",
  "districts": [
    {{
      "district_id": "選挙区ID",
      "predicted_winner": {{
        "name": "候補者名",
        "party_id": "政党ID"
      }},
      "confidence": "high/medium/low",
      "confidence_score": 0.0,
      "analysis": "統合分析テキスト（200-400字）",
      "key_factors": ["決定要因1", "決定要因2", "決定要因3"],
      "candidate_ranking": [
        {{"rank": 1, "name": "候補者名", "party_id": "政党ID"}},
        {{"rank": 2, "name": "候補者名", "party_id": "政党ID"}}
      ],
      "data_consistency": "consistent/partially_inconsistent/inconsistent",
      "news_vs_sns_gap": "分析間の乖離の説明"
    }}
  ],
  "prefecture_summary": "都道府県全体の情勢総括（300字程度）"
}}
"""

CLAUDE_PROPORTIONAL_PROMPT = """
あなたは日本の衆議院選挙の比例代表予測を行うAIアナリストです。
今日は {today} です。

以下の比例ブロックの政党別予測議席数を算出してください。

【対象比例ブロック】
{block_name}（定数: {total_seats}議席）
対象都道府県: {prefectures}

【小選挙区の予測結果（同ブロック内）】
{district_predictions}

【各政党の基礎情報】
{parties_data}

以下の基準で予測してください：
1. 小選挙区での勝敗傾向から政党支持率を推定
2. 都市部・地方のバランスを考慮
3. 最新の世論調査動向を反映
4. ドント方式による議席配分を想定

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください：
{{
  "block_id": "{block_id}",
  "block_name": "{block_name}",
  "total_seats": {total_seats},
  "party_predictions": [
    {{
      "party_id": "政党ID",
      "predicted_seats": 0,
      "vote_share_estimate": 0.0,
      "reasoning": "予測根拠"
    }}
  ],
  "analysis_summary": "ブロック全体の分析（200字程度）"
}}
"""
