"""Seed prediction data for all 289 districts and 11 proportional blocks.

Generates realistic prediction data based on incumbency, party strength
by region, and recent Japanese election trends. Data is deterministic
(seeded random) for reproducibility.
"""

from __future__ import annotations

import json
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Candidate, District, Prediction, PredictionHistory
from app.models.prediction_history import ProportionalPrediction

BATCH_ID = "2026-02-08_seed"

# Regional party strength modifiers (base win probability adjustments).
# Positive = stronger in that region, negative = weaker.
REGIONAL_STRENGTH: dict[str, dict[str, float]] = {
    "北海道": {"chudo": 0.10, "ldp": -0.05},
    "東北": {"ldp": 0.05, "chudo": 0.05},
    "北関東": {"ldp": 0.05, "dpfp": 0.03},
    "南関東": {"ldp": 0.0, "chudo": 0.05, "dpfp": 0.03},
    "東京": {"chudo": 0.05, "ldp": -0.05, "dpfp": 0.05, "reiwa": 0.03},
    "北陸信越": {"ldp": 0.10},
    "東海": {"ldp": 0.0, "dpfp": 0.10, "genzei": 0.08},
    "近畿": {"ishin": 0.20, "ldp": -0.10, "chudo": -0.10},
    "中国": {"ldp": 0.15},
    "四国": {"ldp": 0.10},
    "九州": {"ldp": 0.10, "chudo": -0.05},
}

# Map prefecture to region
PREFECTURE_REGION: dict[str, str] = {
    "北海道": "北海道",
    "青森県": "東北", "岩手県": "東北", "宮城県": "東北",
    "秋田県": "東北", "山形県": "東北", "福島県": "東北",
    "茨城県": "北関東", "栃木県": "北関東", "群馬県": "北関東", "埼玉県": "北関東",
    "千葉県": "南関東", "神奈川県": "南関東", "山梨県": "南関東",
    "東京都": "東京",
    "新潟県": "北陸信越", "富山県": "北陸信越", "石川県": "北陸信越",
    "福井県": "北陸信越", "長野県": "北陸信越",
    "岐阜県": "東海", "静岡県": "東海", "愛知県": "東海", "三重県": "東海",
    "滋賀県": "近畿", "京都府": "近畿", "大阪府": "近畿",
    "兵庫県": "近畿", "奈良県": "近畿", "和歌山県": "近畿",
    "鳥取県": "中国", "島根県": "中国", "岡山県": "中国",
    "広島県": "中国", "山口県": "中国",
    "徳島県": "四国", "香川県": "四国", "愛媛県": "四国", "高知県": "四国",
    "福岡県": "九州", "佐賀県": "九州", "長崎県": "九州",
    "熊本県": "九州", "大分県": "九州", "宮崎県": "九州",
    "鹿児島県": "九州", "沖縄県": "九州",
}

# Base win rates for parties (reflects 2024-era trends where LDP weakened)
BASE_WIN_RATE: dict[str, float] = {
    "ldp": 0.38,
    "chudo": 0.30,
    "ishin": 0.08,
    "dpfp": 0.08,
    "jcp": 0.02,
    "reiwa": 0.03,
    "sansei": 0.01,
    "genzei": 0.02,
    "hoshuto": 0.02,
    "shamin": 0.01,
    "mirai": 0.01,
    "shoha": 0.005,
    "independent": 0.04,
}

# Incumbency bonus
INCUMBENT_BONUS = 0.15

# Key factors templates
KEY_FACTORS_TEMPLATES: dict[str, list[str]] = {
    "ldp": [
        "自民党の組織票が依然強固",
        "政権与党としての知名度を活用",
        "地元経済界からの支持",
        "公明党との選挙協力",
    ],
    "chudo": [
        "野党共闘による票の集約",
        "政権批判票の受け皿",
        "連合系労組の支援",
        "政治改革への期待感",
    ],
    "ishin": [
        "維新の改革路線への期待",
        "大阪での高い支持率の波及",
        "若年層からの支持が強い",
        "既存政党への不満の受け皿",
    ],
    "dpfp": [
        "玉木代表の発信力",
        "減税政策への支持",
        "若年・中間層からの支持拡大",
        "SNSでの発信力",
    ],
    "reiwa": [
        "消費税廃止の訴求力",
        "SNSを活用した選挙戦略",
        "若年層の無党派層を取り込み",
    ],
    "independent": [
        "地元密着の政治活動",
        "無党派層への浸透",
        "特定政党に属さない柔軟さ",
    ],
}

# Analysis summary templates
ANALYSIS_TEMPLATES = {
    "high": [
        "{party}の{candidate}が安定した支持基盤を持ち、当選が有力。対抗馬との差は大きい。",
        "現職の{candidate}（{party}）が高い知名度と実績で他候補をリード。",
        "{candidate}（{party}）が地元の強固な支持基盤と組織力で優位に選挙戦を展開。",
    ],
    "medium": [
        "{party}の{candidate}がやや優位だが、{rival_party}候補の追い上げに注意が必要。",
        "現職{candidate}（{party}）が先行するが、{rival_party}の新人候補が無党派層で浸透中。",
        "{candidate}（{party}）と{rival_party}候補の差は縮まりつつあり、終盤の情勢次第。",
    ],
    "low": [
        "{party}の{candidate}と{rival_party}候補が接戦を展開。無党派層の動向が勝敗を左右。",
        "極めて拮抗した情勢。{candidate}（{party}）と{rival_party}候補の差はわずか。",
        "三つ巴の様相。{candidate}（{party}）がやや先行も予断を許さない展開。",
    ],
}

# Proportional block seat distribution (realistic for 2024-era trends)
PROPORTIONAL_SEATS: dict[str, dict[str, tuple[int, float]]] = {
    # block_id: {party_id: (seats, vote_share)}
    "hokkaido": {
        "ldp": (2, 0.25), "chudo": (3, 0.32), "ishin": (1, 0.10),
        "dpfp": (1, 0.12), "jcp": (0, 0.06), "reiwa": (1, 0.08),
        "sansei": (0, 0.04), "hoshuto": (0, 0.03),
    },
    "tohoku": {
        "ldp": (4, 0.30), "chudo": (4, 0.28), "ishin": (1, 0.08),
        "dpfp": (1, 0.10), "jcp": (1, 0.07), "reiwa": (1, 0.08),
        "sansei": (0, 0.05), "hoshuto": (0, 0.04),
    },
    "kitakanto": {
        "ldp": (6, 0.28), "chudo": (5, 0.25), "ishin": (2, 0.10),
        "dpfp": (3, 0.14), "jcp": (1, 0.06), "reiwa": (1, 0.07),
        "sansei": (1, 0.05), "hoshuto": (0, 0.05),
    },
    "minamikanto": {
        "ldp": (7, 0.27), "chudo": (7, 0.26), "ishin": (2, 0.09),
        "dpfp": (3, 0.13), "jcp": (1, 0.06), "reiwa": (2, 0.08),
        "sansei": (1, 0.05), "hoshuto": (0, 0.06),
    },
    "tokyo": {
        "ldp": (5, 0.24), "chudo": (5, 0.25), "ishin": (2, 0.10),
        "dpfp": (3, 0.14), "jcp": (1, 0.07), "reiwa": (2, 0.09),
        "sansei": (0, 0.04), "hoshuto": (1, 0.07),
    },
    "hokurikushinetsu": {
        "ldp": (4, 0.35), "chudo": (3, 0.25), "ishin": (1, 0.08),
        "dpfp": (1, 0.12), "jcp": (0, 0.06), "reiwa": (1, 0.07),
        "sansei": (0, 0.04), "hoshuto": (0, 0.03),
    },
    "tokai": {
        "ldp": (6, 0.27), "chudo": (5, 0.22), "ishin": (2, 0.09),
        "dpfp": (4, 0.18), "jcp": (1, 0.06), "reiwa": (1, 0.07),
        "sansei": (1, 0.05), "genzei": (1, 0.06),
    },
    "kinki": {
        "ldp": (5, 0.20), "chudo": (4, 0.16), "ishin": (11, 0.35),
        "dpfp": (3, 0.10), "jcp": (2, 0.06), "reiwa": (2, 0.06),
        "sansei": (1, 0.04), "hoshuto": (0, 0.03),
    },
    "chugoku": {
        "ldp": (4, 0.35), "chudo": (3, 0.25), "ishin": (1, 0.10),
        "dpfp": (1, 0.10), "jcp": (0, 0.06), "reiwa": (1, 0.07),
        "sansei": (0, 0.04), "hoshuto": (0, 0.03),
    },
    "shikoku": {
        "ldp": (2, 0.32), "chudo": (2, 0.27), "ishin": (1, 0.12),
        "dpfp": (1, 0.12), "jcp": (0, 0.06), "reiwa": (0, 0.06),
        "sansei": (0, 0.03), "hoshuto": (0, 0.02),
    },
    "kyushu": {
        "ldp": (7, 0.30), "chudo": (5, 0.23), "ishin": (2, 0.10),
        "dpfp": (2, 0.10), "jcp": (1, 0.06), "reiwa": (2, 0.08),
        "sansei": (1, 0.06), "hoshuto": (0, 0.04), "shamin": (0, 0.03),
    },
}


def _pick_winner_and_score(
    candidates: list[dict], prefecture: str, rng: random.Random
) -> tuple[dict, float, str]:
    """Pick a winner from candidates using weighted probabilities.

    Returns (winner_candidate_dict, confidence_score, confidence_label).
    """
    region = PREFECTURE_REGION.get(prefecture, "")
    regional_mod = REGIONAL_STRENGTH.get(region, {})

    weights: list[float] = []
    for c in candidates:
        party = c["party_id"]
        base = BASE_WIN_RATE.get(party, 0.01)
        reg = regional_mod.get(party, 0.0)
        inc = INCUMBENT_BONUS if c.get("is_incumbent") else 0.0
        # Extra bonus for higher previous_wins
        prev_bonus = min(c.get("previous_wins", 0) * 0.03, 0.12)
        w = max(base + reg + inc + prev_bonus, 0.01)
        weights.append(w)

    # Normalize
    total = sum(weights)
    probs = [w / total for w in weights]

    # Pick winner
    winner_idx = rng.choices(range(len(candidates)), weights=probs, k=1)[0]
    winner = candidates[winner_idx]

    # Calculate margin (difference between winner prob and runner-up)
    sorted_probs = sorted(probs, reverse=True)
    if len(sorted_probs) >= 2:
        margin = sorted_probs[0] - sorted_probs[1]
    else:
        margin = sorted_probs[0]

    # Map margin to confidence score (0.3 - 0.95)
    confidence_score = min(0.95, max(0.30, 0.40 + margin * 2.0 + rng.uniform(-0.1, 0.1)))

    if confidence_score >= 0.70:
        confidence = "high"
    elif confidence_score >= 0.50:
        confidence = "medium"
    else:
        confidence = "low"

    return winner, round(confidence_score, 3), confidence


def _generate_analysis(
    winner_name: str,
    winner_party: str,
    candidates: list[dict],
    confidence: str,
    rng: random.Random,
) -> str:
    """Generate an analysis summary."""
    party_names_ja = {
        "ldp": "自民", "chudo": "中道", "ishin": "維新",
        "dpfp": "国民", "jcp": "共産", "reiwa": "れいわ",
        "sansei": "参政", "genzei": "減税", "hoshuto": "保守",
        "shamin": "社民", "mirai": "みらい", "shoha": "諸派",
        "independent": "無所属",
    }
    party_ja = party_names_ja.get(winner_party, winner_party)

    # Find rival party
    rival_parties = [c["party_id"] for c in candidates if c["party_id"] != winner_party]
    rival_party = party_names_ja.get(rng.choice(rival_parties) if rival_parties else "chudo", "野党")

    templates = ANALYSIS_TEMPLATES.get(confidence, ANALYSIS_TEMPLATES["medium"])
    template = rng.choice(templates)
    return template.format(
        party=party_ja,
        candidate=winner_name,
        rival_party=rival_party,
    )


def _generate_key_factors(party_id: str, rng: random.Random) -> list[str]:
    """Pick 2-3 key factors for the prediction."""
    factors = KEY_FACTORS_TEMPLATES.get(party_id, [
        "地域での知名度の高さ",
        "効果的な選挙戦略",
        "支持基盤の確保",
    ])
    return rng.sample(factors, min(len(factors), rng.randint(2, 3)))


async def seed_predictions(session: AsyncSession) -> None:
    """Seed predictions for all 289 districts."""
    existing = (await session.execute(select(Prediction))).scalars().first()
    if existing:
        return

    rng = random.Random(42)  # Deterministic

    # Load all districts with their candidates
    districts_result = await session.execute(select(District))
    districts = districts_result.scalars().all()

    for district in districts:
        cand_result = await session.execute(
            select(Candidate).where(Candidate.district_id == district.id)
        )
        candidates = cand_result.scalars().all()

        if not candidates:
            continue

        cand_dicts = [
            {
                "id": c.id,
                "name": c.name,
                "party_id": c.party_id,
                "is_incumbent": c.is_incumbent,
                "previous_wins": c.previous_wins,
            }
            for c in candidates
        ]

        winner, confidence_score, confidence = _pick_winner_and_score(
            cand_dicts, district.prefecture, rng
        )

        analysis = _generate_analysis(
            winner["name"], winner["party_id"], cand_dicts, confidence, rng
        )
        key_factors = _generate_key_factors(winner["party_id"], rng)

        # Build candidate rankings
        rankings = []
        for c in cand_dicts:
            rank_score = rng.uniform(0.1, 0.9)
            if c["id"] == winner["id"]:
                rank_score = confidence_score
            rankings.append({
                "candidate_name": c["name"],
                "party_id": c["party_id"],
                "score": round(rank_score, 3),
            })
        rankings.sort(key=lambda x: -x["score"])

        # News and SNS summaries
        party_names_ja = {
            "ldp": "自民", "chudo": "中道", "ishin": "維新",
            "dpfp": "国民", "jcp": "共産", "reiwa": "れいわ",
            "sansei": "参政", "genzei": "減税", "hoshuto": "保守",
            "shamin": "社民", "mirai": "みらい", "shoha": "諸派",
            "independent": "無所属",
        }
        winner_party_ja = party_names_ja.get(winner["party_id"], "")

        news_summaries = [
            f"地元メディアでは{winner_party_ja}の{winner['name']}候補がリードと報道。",
            f"新聞各社の世論調査では{winner_party_ja}候補が一歩リードの展開。",
            f"選挙区情勢分析では{winner_party_ja}がやや優勢との見方が多い。",
        ]
        sns_summaries = [
            f"SNS上では{winner_party_ja}候補への言及が増加傾向。ポジティブな反応が多い。",
            f"Twitter分析では{winner['name']}候補のエンゲージメント率が高い。",
            f"YouTube政治チャンネルでも{winner_party_ja}候補への注目度が上昇中。",
        ]

        session.add(Prediction(
            district_id=district.id,
            predicted_winner_candidate_id=winner["id"],
            predicted_winner_party_id=winner["party_id"],
            confidence=confidence,
            confidence_score=confidence_score,
            analysis_summary=analysis,
            news_summary=rng.choice(news_summaries),
            sns_summary=rng.choice(sns_summaries),
            key_factors=json.dumps(key_factors, ensure_ascii=False),
            candidate_rankings=json.dumps(rankings, ensure_ascii=False),
            prediction_batch_id=BATCH_ID,
            updated_at=datetime(2026, 2, 8, 10, 0, 0),
        ))

        session.add(PredictionHistory(
            district_id=district.id,
            predicted_winner_party_id=winner["party_id"],
            confidence=confidence,
            confidence_score=confidence_score,
            prediction_batch_id=BATCH_ID,
        ))

    await session.commit()


async def seed_proportional_predictions(session: AsyncSession) -> None:
    """Seed proportional prediction data for all 11 blocks."""
    existing = (await session.execute(select(ProportionalPrediction))).scalars().first()
    if existing:
        return

    for block_id, party_seats in PROPORTIONAL_SEATS.items():
        for party_id, (seats, vote_share) in party_seats.items():
            if seats == 0 and vote_share < 0.05:
                # Skip very minor entries to keep data clean
                continue

            party_names_ja = {
                "ldp": "自民", "chudo": "中道", "ishin": "維新",
                "dpfp": "国民", "jcp": "共産", "reiwa": "れいわ",
                "sansei": "参政", "genzei": "減税", "hoshuto": "保守",
                "shamin": "社民", "mirai": "みらい",
            }
            party_ja = party_names_ja.get(party_id, party_id)

            if seats >= 4:
                summary = f"{party_ja}はこのブロックで安定した支持を確保し、{seats}議席を獲得と予測。"
            elif seats >= 2:
                summary = f"{party_ja}は一定の支持を得て{seats}議席の獲得を見込む。"
            elif seats == 1:
                summary = f"{party_ja}は1議席を辛うじて確保する見通し。"
            else:
                summary = f"{party_ja}は議席獲得には至らないものの、得票率{vote_share*100:.1f}%を確保。"

            session.add(ProportionalPrediction(
                block_id=block_id,
                party_id=party_id,
                predicted_seats=seats,
                vote_share_estimate=vote_share,
                analysis_summary=summary,
                prediction_batch_id=BATCH_ID,
                updated_at=datetime(2026, 2, 8, 10, 0, 0),
            ))

    await session.commit()


async def seed_all_predictions(session: AsyncSession) -> None:
    """Seed both district predictions and proportional predictions."""
    await seed_predictions(session)
    await seed_proportional_predictions(session)
