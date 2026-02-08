"""
記憶付きLLM投票モジュール（v10b）

通常のキャリブレーション付きプロンプトに、記憶コンテキスト（実選挙データ、
経済指標、過去シミュレーション結果、キャリブレーション補正）を注入する。
"""
from __future__ import annotations

from ..prompts import CALIBRATED_SYSTEM_PROMPT, build_calibrated_batch_prompt


MEMORY_SYSTEM_PROMPT = CALIBRATED_SYSTEM_PROMPT + """

追加指示（記憶システム）:
- この選挙区に関する過去の実際の選挙結果と現在の経済状況が提供されます
- 過去の実選挙結果は重要な参考情報です。特に直近の2024年衆院選と2025年参院選の
  結果は有権者の投票傾向を理解する上で重要です
- 経済状況（物価高、実質賃金、雇用）は有権者の投票行動に影響します
  → 物価高は与党への不満要因、株高・雇用堅調は与党への支持要因
- 過去のシミュレーション結果が提供される場合は参考情報として使用してください
  ただし、今回の判断に過度に影響されないようにしてください
- キャリブレーション補正シグナルが示されている場合、過去に特定の政党を
  過剰/過少に予測していた傾向を認識し、今回の予測で修正を試みてください
- 最も重要な判断基準は今回の選挙固有の状況です"""


def build_memory_augmented_prompt(
    district_name: str,
    area_description: str,
    candidates: list[dict],
    district_context: dict,
    personas: list[dict],
    memory_context: str,
    weather: str = "大雪・強烈寒波",
    political_climate: dict | None = None,
) -> str:
    """記憶コンテキスト付きプロンプトを構築する"""

    base_prompt = build_calibrated_batch_prompt(
        district_name=district_name,
        area_description=area_description,
        candidates=candidates,
        district_context=district_context,
        personas=personas,
        weather=weather,
        political_climate=political_climate,
    )

    if not memory_context:
        return base_prompt

    # 「## タスク」セクションの前に記憶コンテキストを挿入
    task_marker = "## タスク"
    if task_marker in base_prompt:
        parts = base_prompt.split(task_marker, 1)
        return parts[0] + memory_context + "\n\n" + task_marker + parts[1]

    # マーカーが見つからない場合はプロンプト末尾に追加
    return base_prompt + "\n\n" + memory_context
