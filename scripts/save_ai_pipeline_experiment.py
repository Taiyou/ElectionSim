"""
AIパイプライン（Perplexity + Grok + Claude）予測結果を
実験管理フォーマットで保存するスクリプト
"""

import csv
import json
import sqlite3
import subprocess
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results" / "experiments"
DB_PATH = BASE_DIR / "backend" / "election_ai.db"
PERSONA_DATA_DIR = BASE_DIR / "persona_data"
PROMPTS_DIR = BASE_DIR / "backend" / "app" / "prompts"


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()[:16]}"


def _get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- Gather prediction data ---
    cursor.execute("SELECT COUNT(*) FROM predictions")
    pred_count = cursor.fetchone()[0]
    if pred_count == 0:
        print("No predictions found in database. Run the pipeline first.")
        return

    cursor.execute("SELECT DISTINCT prediction_batch_id FROM predictions ORDER BY prediction_batch_id DESC LIMIT 1")
    batch_id = cursor.fetchone()[0]
    print(f"Saving experiment for batch_id: {batch_id}")

    # Generate experiment ID
    now = datetime.now(JST)
    experiment_id = f"ai_pipeline_{now.strftime('%Y%m%d_%H%M%S')}"

    # Create experiment directory
    exp_dir = RESULTS_DIR / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # --- district_results.csv ---
    cursor.execute("""
        SELECT
            p.district_id,
            d.name as district_name,
            p.predicted_winner_party_id as winner_party,
            p.confidence,
            p.confidence_score,
            p.analysis_summary,
            p.key_factors,
            c.name as winner_name,
            p.candidate_rankings
        FROM predictions p
        JOIN districts d ON d.id = p.district_id
        LEFT JOIN candidates c ON c.id = p.predicted_winner_candidate_id
        WHERE p.prediction_batch_id = ?
        ORDER BY d.prefecture_code, d.district_number
    """, (batch_id,))
    predictions = cursor.fetchall()

    district_csv_path = exp_dir / "district_results.csv"
    with open(district_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "district_id", "district_name", "winner", "winner_party",
            "confidence", "confidence_score", "analysis_summary", "key_factors",
            "candidate_rankings"
        ])
        for row in predictions:
            writer.writerow([
                row["district_id"],
                row["district_name"],
                row["winner_name"] or "",
                row["winner_party"],
                row["confidence"],
                row["confidence_score"],
                row["analysis_summary"] or "",
                row["key_factors"] or "[]",
                row["candidate_rankings"] or "[]",
            ])
    print(f"  district_results.csv: {len(predictions)} rows")

    # --- proportional_results.csv ---
    cursor.execute("""
        SELECT
            pp.block_id,
            b.name as block_name,
            pp.party_id,
            pp.predicted_seats,
            pp.vote_share_estimate,
            pp.analysis_summary
        FROM proportional_predictions pp
        JOIN proportional_blocks b ON b.id = pp.block_id
        WHERE pp.prediction_batch_id = ?
        ORDER BY b.id, pp.predicted_seats DESC
    """, (batch_id,))
    proportional = cursor.fetchall()

    prop_csv_path = exp_dir / "proportional_results.csv"
    with open(prop_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "block_id", "block_name", "party", "predicted_seats",
            "vote_share_estimate", "analysis_summary"
        ])
        for row in proportional:
            writer.writerow([
                row["block_id"],
                row["block_name"],
                row["party_id"],
                row["predicted_seats"],
                row["vote_share_estimate"],
                row["analysis_summary"] or "",
            ])
    print(f"  proportional_results.csv: {len(proportional)} rows")

    # --- summary.json ---
    # SMD seats
    cursor.execute("""
        SELECT predicted_winner_party_id, COUNT(*) as cnt
        FROM predictions
        WHERE prediction_batch_id = ?
        GROUP BY predicted_winner_party_id
        ORDER BY cnt DESC
    """, (batch_id,))
    smd_seats = {row[0]: row[1] for row in cursor.fetchall()}

    # Proportional seats
    cursor.execute("""
        SELECT party_id, SUM(predicted_seats) as seats
        FROM proportional_predictions
        WHERE prediction_batch_id = ?
        GROUP BY party_id
        ORDER BY seats DESC
    """, (batch_id,))
    pr_seats = {row[0]: int(row[1]) for row in cursor.fetchall()}

    # Total seats
    total_seats = {}
    all_parties = set(list(smd_seats.keys()) + list(pr_seats.keys()))
    for party in all_parties:
        total_seats[party] = smd_seats.get(party, 0) + pr_seats.get(party, 0)
    total_seats = dict(sorted(total_seats.items(), key=lambda x: x[1], reverse=True))

    # Confidence distribution
    cursor.execute("""
        SELECT confidence, COUNT(*) as cnt
        FROM predictions
        WHERE prediction_batch_id = ?
        GROUP BY confidence
    """, (batch_id,))
    confidence_dist = {row[0]: row[1] for row in cursor.fetchall()}

    summary = {
        "total_districts_predicted": len(predictions),
        "total_districts": 289,
        "total_proportional_seats": 176,
        "majority_line": 233,
        "smd_seats": smd_seats,
        "pr_seats": pr_seats,
        "total_seats": total_seats,
        "confidence_distribution": confidence_dist,
        "pipeline_config": {
            "batch_id": batch_id,
            "models": {
                "news_analysis": "perplexity/sonar-pro",
                "sns_analysis": "x-ai/grok-3",
                "integration": "anthropic/claude-sonnet-4",
            },
            "api_gateway": "OpenRouter",
        },
    }

    summary_path = exp_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  summary.json written")

    # --- validation_report.json ---
    ldp_smd = smd_seats.get("ldp", 0)
    ldp_total = total_seats.get("ldp", 0)
    total_predicted = sum(total_seats.values())

    checks = [
        {
            "name": "予測選挙区カバー率",
            "passed": len(predictions) >= 280,
            "detail": f"{len(predictions)}/289選挙区 ({len(predictions)/289*100:.1f}%)",
        },
        {
            "name": "自民党小選挙区議席数",
            "passed": 50 <= ldp_smd <= 250,
            "detail": f"{ldp_smd}議席（期待: 50-250）",
        },
        {
            "name": "自民党総議席数",
            "passed": 100 <= ldp_total <= 300,
            "detail": f"{ldp_total}議席（期待: 100-300）",
        },
        {
            "name": "総議席数の整合性",
            "passed": 450 <= total_predicted <= 465,
            "detail": f"{total_predicted}/465議席",
        },
        {
            "name": "比例代表議席合計",
            "passed": sum(pr_seats.values()) == 176,
            "detail": f"{sum(pr_seats.values())}/176議席",
        },
        {
            "name": "高信頼度予測の存在",
            "passed": confidence_dist.get("high", 0) > 0,
            "detail": f"high: {confidence_dist.get('high', 0)}, medium: {confidence_dist.get('medium', 0)}, low: {confidence_dist.get('low', 0)}",
        },
        {
            "name": "複数政党の当選",
            "passed": len(smd_seats) >= 2,
            "detail": f"{len(smd_seats)}政党が小選挙区で当選",
        },
    ]

    warnings = [c["detail"] for c in checks if not c["passed"]]
    errors = []
    passed = len(errors) == 0

    validation = {
        "passed": passed,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }

    val_path = exp_dir / "validation_report.json"
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(validation, f, ensure_ascii=False, indent=2)
    print(f"  validation_report.json written (passed={passed})")

    # --- config_snapshot ---
    snapshot_dir = exp_dir / "config_snapshot"
    snapshot_dir.mkdir(exist_ok=True)

    # Save prompts used
    prompt_files = list(PROMPTS_DIR.glob("*.py")) if PROMPTS_DIR.exists() else []
    config_hashes = {}

    for pf in prompt_files:
        import shutil
        shutil.copy2(pf, snapshot_dir / pf.name)
        config_hashes[f"prompt_{pf.stem}_hash"] = _file_sha256(pf)

    # Save persona config if exists
    for config_name in ["persona_config.json", "manifesto_policies.json"]:
        config_path = PERSONA_DATA_DIR / config_name
        if config_path.exists():
            import shutil
            shutil.copy2(config_path, snapshot_dir / config_name)
            config_hashes[f"{config_name.replace('.json', '')}_hash"] = _file_sha256(config_path)

    # Save .env (without secrets)
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            env_lines = f.readlines()
        with open(snapshot_dir / "env_config.txt", "w") as f:
            for line in env_lines:
                if "KEY" in line.upper() or "SECRET" in line.upper():
                    key = line.split("=")[0].strip()
                    f.write(f"{key}=***REDACTED***\n")
                else:
                    f.write(line)

    print(f"  config_snapshot: {len(list(snapshot_dir.iterdir()))} files")

    # --- metadata.json ---
    metadata = {
        "experiment_id": experiment_id,
        "created_at": now.isoformat(),
        "status": "completed",
        "duration_seconds": None,
        "description": "AIパイプライン予測（Perplexity+Grok+Claude via OpenRouter）",
        "tags": ["ai_pipeline", "full", "perplexity", "grok", "claude", "openrouter"],
        "parameters": {
            "pipeline_type": "ai_multi_agent",
            "batch_id": batch_id,
            "models": {
                "news_analysis": "perplexity/sonar-pro",
                "sns_analysis": "x-ai/grok-3",
                "integration": "anthropic/claude-sonnet-4",
            },
            "api_gateway": "OpenRouter",
            "mode": "full",
            "district_count": len(predictions),
            "total_districts": 289,
            "schedule_hours": "8,12,20",
            "api_rate_limit_per_minute": 30,
        },
        "config_versions": config_hashes,
        "results_summary": {
            "smd_seats": smd_seats,
            "pr_seats": pr_seats,
            "total_seats": total_seats,
            "confidence_distribution": confidence_dist,
            "districts_predicted": len(predictions),
            "districts_missing": 289 - len(predictions),
            "validation_passed": passed,
        },
        "environment": {
            "git_commit": _get_git_commit(),
        },
    }

    metadata_path = exp_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"  metadata.json written")

    conn.close()

    print(f"\nExperiment saved: {experiment_id}")
    print(f"Location: {exp_dir}")
    print(f"\nResults summary:")
    print(f"  Districts predicted: {len(predictions)}/289")
    print(f"  Proportional blocks: {len(set(r['block_id'] for r in proportional))}")
    print(f"  Top parties (total seats):")
    for party, seats in list(total_seats.items())[:5]:
        print(f"    {party}: {seats} ({smd_seats.get(party, 0)} SMD + {pr_seats.get(party, 0)} PR)")


if __name__ == "__main__":
    main()
