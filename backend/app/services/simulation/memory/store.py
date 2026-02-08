"""
記憶ストア（v10b）

SQLiteベースの3層記憶システム:
1. エピソード記憶: 各シミュレーション実行の選挙区結果
2. キャリブレーション記憶: LLMバイアスの補正シグナル
3. トレンド記憶: 複数実行にわたる政党支持率の時系列傾向

加えて、実選挙データ（past_elections.json）と経済指標（economic_context.json）を
読み込んでプロンプト用コンテキストを生成する。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

_FILE_DIR = Path(__file__).resolve().parent  # .../memory/
_BACKEND_DIR = _FILE_DIR.parent.parent.parent.parent  # .../backend/ or /app/
BASE_DIR = _BACKEND_DIR.parent
PERSONA_DIR = BASE_DIR / "persona_data"
MEMORY_DIR = BASE_DIR / "memory"
DB_PATH = MEMORY_DIR / "agent_memory.db"


class MemoryStore:
    """SQLiteベースの記憶ストア"""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # 実データを読み込み
        self._past_elections = self._load_past_elections()
        self._economic_context = self._load_economic_context()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    district_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    total_personas INTEGER,
                    turnout_rate REAL,
                    winner_party TEXT,
                    party_vote_shares TEXT,
                    method TEXT,
                    calibration_strength REAL
                );

                CREATE TABLE IF NOT EXISTS calibration_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    district_id TEXT NOT NULL,
                    party_id TEXT NOT NULL,
                    target_share REAL,
                    predicted_share REAL,
                    correction_needed REAL,
                    timestamp TEXT NOT NULL,
                    experiment_id TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trends (
                    district_id TEXT NOT NULL,
                    party_id TEXT NOT NULL,
                    run_count INTEGER DEFAULT 0,
                    avg_vote_share REAL,
                    stddev_vote_share REAL,
                    trend_direction TEXT DEFAULT 'stable',
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (district_id, party_id)
                );

                CREATE INDEX IF NOT EXISTS idx_episodes_district
                    ON episodes(district_id);
                CREATE INDEX IF NOT EXISTS idx_calibration_district
                    ON calibration_signals(district_id);
            """)

    # ------------------------------------------------------------------
    # 実データ読み込み
    # ------------------------------------------------------------------
    def _load_past_elections(self) -> dict:
        path = PERSONA_DIR / "past_elections.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_economic_context(self) -> dict:
        path = PERSONA_DIR / "economic_context.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    # ------------------------------------------------------------------
    # エピソード記憶 CRUD
    # ------------------------------------------------------------------
    def store_episode(
        self,
        experiment_id: str,
        district_id: str,
        total_personas: int,
        turnout_rate: float,
        winner_party: str,
        party_vote_shares: dict,
        method: str = "llm_demographic",
        calibration_strength: float = 0.3,
    ):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO episodes
                (experiment_id, district_id, timestamp, total_personas,
                 turnout_rate, winner_party, party_vote_shares, method, calibration_strength)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment_id, district_id, now, total_personas,
                turnout_rate, winner_party, json.dumps(party_vote_shares),
                method, calibration_strength,
            ))

    def get_district_history(self, district_id: str, limit: int = 5) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM episodes
                WHERE district_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (district_id, limit)).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # キャリブレーション記憶
    # ------------------------------------------------------------------
    def store_calibration_signal(
        self,
        district_id: str,
        party_id: str,
        target_share: float,
        predicted_share: float,
        experiment_id: str,
    ):
        now = datetime.utcnow().isoformat()
        correction = target_share - predicted_share
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO calibration_signals
                (district_id, party_id, target_share, predicted_share,
                 correction_needed, timestamp, experiment_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                district_id, party_id, target_share, predicted_share,
                correction, now, experiment_id,
            ))

    def get_calibration_history(self, district_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT party_id,
                       AVG(correction_needed) as avg_correction,
                       COUNT(*) as signal_count,
                       MAX(timestamp) as latest
                FROM calibration_signals
                WHERE district_id = ?
                GROUP BY party_id
            """, (district_id,)).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # トレンド記憶
    # ------------------------------------------------------------------
    def update_trends(self, district_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            episodes = conn.execute("""
                SELECT party_vote_shares FROM episodes
                WHERE district_id = ?
                ORDER BY timestamp DESC
                LIMIT 20
            """, (district_id,)).fetchall()

            if not episodes:
                return

            party_shares: dict[str, list[float]] = {}
            for ep in episodes:
                shares = json.loads(ep["party_vote_shares"])
                for party, share in shares.items():
                    party_shares.setdefault(party, []).append(float(share))

            now = datetime.utcnow().isoformat()
            for party, shares in party_shares.items():
                avg = sum(shares) / len(shares)
                stddev = (sum((s - avg) ** 2 for s in shares) / len(shares)) ** 0.5 if len(shares) > 1 else 0.0

                if len(shares) >= 4:
                    half = len(shares) // 2
                    recent = sum(shares[:half]) / half
                    older = sum(shares[half:]) / (len(shares) - half)
                    if recent - older > 0.02:
                        direction = "increasing"
                    elif older - recent > 0.02:
                        direction = "decreasing"
                    else:
                        direction = "stable"
                else:
                    direction = "stable"

                conn.execute("""
                    INSERT INTO trends (district_id, party_id, run_count,
                                        avg_vote_share, stddev_vote_share,
                                        trend_direction, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(district_id, party_id) DO UPDATE SET
                        run_count = ?,
                        avg_vote_share = ?,
                        stddev_vote_share = ?,
                        trend_direction = ?,
                        last_updated = ?
                """, (
                    district_id, party, len(shares), avg, stddev, direction, now,
                    len(shares), avg, stddev, direction, now,
                ))

    # ------------------------------------------------------------------
    # プロンプト用コンテキスト生成
    # ------------------------------------------------------------------
    def get_memory_context_for_prompt(self, district_id: str) -> str:
        """LLMプロンプトに注入する記憶コンテキストを生成"""
        sections = []

        # 1. 実選挙データ
        election_lines = self._format_election_data(district_id)
        if election_lines:
            sections.append("## 過去の選挙実績（実データ）\n" + election_lines)

        # 2. 経済状況
        econ_lines = self._format_economic_context()
        if econ_lines:
            sections.append("## 現在の経済状況（2026年1月時点）\n" + econ_lines)

        # 3. エピソード記憶
        history = self.get_district_history(district_id, limit=3)
        if history:
            lines = [f"この選挙区の過去{len(history)}回のシミュレーション結果:"]
            for h in history:
                shares = json.loads(h.get("party_vote_shares", "{}"))
                top_3 = sorted(shares.items(), key=lambda x: -float(x[1]))[:3]
                share_str = ", ".join(f"{p}:{float(s):.1%}" for p, s in top_3)
                lines.append(
                    f"  - {h['experiment_id']}: 当選={h['winner_party']}, "
                    f"得票率={share_str}, 投票率={h['turnout_rate']:.1%}"
                )
            sections.append("## 過去のシミュレーション記憶（参考）\n" + "\n".join(lines))

        # 4. キャリブレーション記憶
        calibrations = self.get_calibration_history(district_id)
        if calibrations:
            lines = ["キャリブレーション補正シグナル:"]
            for c in calibrations:
                direction = "過剰" if c["avg_correction"] < 0 else "不足"
                lines.append(
                    f"  - {c['party_id']}: 過去平均{abs(c['avg_correction']):.1%}{direction}"
                    f" ({c['signal_count']}回の観測)"
                )
            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    def _format_election_data(self, district_id: str) -> str:
        """実選挙データをフォーマット"""
        elections = self._past_elections.get("elections", [])
        if not elections:
            return ""

        party_names = {
            "ldp": "自民", "cdp": "立憲", "ishin": "維新", "dpfp": "国民",
            "jcp": "共産", "reiwa": "れいわ", "sansei": "参政", "komei": "公明",
            "hoshuto": "保守", "shamin": "社民",
        }

        lines = []
        for election in elections:
            eid = election["election_id"]
            etype = election["type"]
            date = election["date"]
            turnout = election.get("national_turnout")
            turnout_str = f"投票率{turnout:.1%}" if turnout else ""

            nat = election.get("national_results", {})
            top_parties = sorted(
                nat.items(),
                key=lambda x: x[1].get("seats", 0) if isinstance(x[1], dict) else 0,
                reverse=True,
            )[:5]

            party_strs = []
            for pid, data in top_parties:
                name = party_names.get(pid, pid)
                seats = data.get("seats", 0) if isinstance(data, dict) else 0
                party_strs.append(f"{name}{seats}")

            trends = election.get("key_trends", [])
            trend_str = f" ※{trends[0]}" if trends else ""

            lines.append(
                f"- {etype}({date}): {', '.join(party_strs)}議席 {turnout_str}{trend_str}"
            )

        return "\n".join(lines)

    def _format_economic_context(self) -> str:
        """経済指標をフォーマット"""
        ec = self._economic_context
        if not ec:
            return ""

        lines = []
        gdp = ec.get("gdp_growth_rate_2025")
        cpi = ec.get("cpi_year_over_year")
        unemp = ec.get("unemployment_rate")
        if gdp is not None and cpi is not None and unemp is not None:
            lines.append(
                f"- GDP成長率: +{gdp:.1%}(2025年度), CPI前年比: +{cpi:.1%}(12月), 失業率: {unemp:.1%}"
            )

        rw_2025 = ec.get("real_wage_change_2025")
        rw_2026 = ec.get("real_wage_forecast_2026")
        if rw_2025 is not None and rw_2026 is not None:
            lines.append(
                f"- 実質賃金: 2025年度{rw_2025:+.1%}(マイナス継続), 2026年度{rw_2026:+.1%}見込み"
            )

        nikkei = ec.get("nikkei225_all_time_high")
        yen = ec.get("yen_usd_rate")
        if nikkei and yen:
            lines.append(f"- 日経平均: {nikkei:,}円(過去最高値更新), 円ドル: {yen:.0f}円台")

        labor = ec.get("labor_market")
        if labor:
            lines.append(f"- {labor}")

        sentiment = ec.get("consumer_sentiment")
        if sentiment:
            lines.append(f"- 生活実感: {sentiment}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # リセット
    # ------------------------------------------------------------------
    def reset(self):
        """全記憶をリセット"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                DELETE FROM episodes;
                DELETE FROM calibration_signals;
                DELETE FROM trends;
            """)
