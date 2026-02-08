"""
実験バージョン管理マネージャー

シミュレーション実験のライフサイクルを管理する:
- 実験ディレクトリの作成
- メタデータの記録
- 設定ファイルのスナップショット
- 実験一覧・ロード
- 実選挙結果のロード
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
RESULTS_DIR = BASE_DIR / "results" / "experiments"
ACTUAL_DIR = RESULTS_DIR / "actual"
PERSONA_DATA_DIR = BASE_DIR / "persona_data"


def _file_sha256(path: Path) -> str:
    """ファイルのSHA256ハッシュを計算"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()[:16]}"


def _get_git_commit() -> str:
    """現在のgit commitハッシュを取得"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _load_factor_weights() -> dict[str, float]:
    """persona_config.json から投票決定要因の重みを取得"""
    config_path = PERSONA_DATA_DIR / "persona_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    factors = config.get("voting_decision_factors", {})
    return {k: v["weight"] for k, v in factors.items() if isinstance(v, dict) and "weight" in v}


class ExperimentManager:
    """実験のライフサイクル管理"""

    def __init__(self):
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    def generate_experiment_id(self, seed: int) -> str:
        """タイムスタンプ + seed から実験IDを生成"""
        now = datetime.now(JST)
        return f"sim_{now.strftime('%Y%m%d_%H%M%S')}_seed{seed}"

    def create_experiment_dir(self, experiment_id: str) -> Path:
        """実験ディレクトリを作成"""
        exp_dir = RESULTS_DIR / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        return exp_dir

    def snapshot_configs(self, experiment_dir: Path) -> dict[str, str]:
        """設定ファイルをスナップショット保存し、ハッシュを返す"""
        snapshot_dir = experiment_dir / "config_snapshot"
        snapshot_dir.mkdir(exist_ok=True)

        hashes = {}
        config_files = {
            "persona_config": PERSONA_DATA_DIR / "persona_config.json",
            "manifesto_policies": PERSONA_DATA_DIR / "manifesto_policies.json",
        }

        for key, src_path in config_files.items():
            if src_path.exists():
                shutil.copy2(src_path, snapshot_dir / src_path.name)
                hashes[f"{key}_hash"] = _file_sha256(src_path)
            else:
                logger.warning(f"設定ファイルが見つかりません: {src_path}")

        return hashes

    def write_metadata(
        self,
        experiment_dir: Path,
        experiment_id: str,
        duration_seconds: float,
        description: str,
        tags: list[str],
        parameters: dict,
        results_summary: dict,
        validation_passed: bool,
    ) -> dict:
        """metadata.json を書き込み"""
        config_hashes = self.snapshot_configs(experiment_dir)
        factor_weights = _load_factor_weights()

        metadata = {
            "experiment_id": experiment_id,
            "created_at": datetime.now(JST).isoformat(),
            "status": "completed",
            "duration_seconds": round(duration_seconds, 2),
            "description": description,
            "tags": tags,
            "parameters": parameters,
            "config_versions": {
                **config_hashes,
                "factor_weights": factor_weights,
            },
            "results_summary": results_summary,
            "environment": {
                "git_commit": _get_git_commit(),
            },
        }

        metadata_path = experiment_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"メタデータ保存: {metadata_path}")
        return metadata

    def write_validation_report(self, experiment_dir: Path, report) -> None:
        """バリデーションレポートをJSONで保存"""
        report_data = {
            "passed": report.passed,
            "checks": report.checks,
            "warnings": report.warnings,
            "errors": report.errors,
        }
        path = experiment_dir / "validation_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

    def list_experiments(self) -> list[dict]:
        """保存済み実験の一覧をメタデータ付きで返す"""
        experiments = []
        if not RESULTS_DIR.exists():
            return experiments

        for exp_dir in sorted(RESULTS_DIR.iterdir()):
            if not exp_dir.is_dir() or exp_dir.name == "actual":
                continue
            metadata_path = exp_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                experiments.append(metadata)

        return experiments

    def load_experiment(self, experiment_id: str) -> dict:
        """指定実験のメタデータと結果を読み込み"""
        exp_dir = RESULTS_DIR / experiment_id
        if not exp_dir.exists():
            raise FileNotFoundError(f"実験が見つかりません: {experiment_id}")

        # メタデータ
        metadata_path = exp_dir / "metadata.json"
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # 選挙区結果
        district_results = []
        csv_path = exp_dir / "district_results.csv"
        if csv_path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 数値型に変換
                    for key in ["total_personas", "turnout_count", "winner_votes", "runner_up_votes", "margin"]:
                        if key in row:
                            row[key] = int(row[key])
                    for key in ["turnout_rate"]:
                        if key in row:
                            row[key] = float(row[key])
                    district_results.append(row)

        # サマリ
        summary = {}
        summary_path = exp_dir / "summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)

        return {
            "metadata": metadata,
            "district_results": district_results,
            "summary": summary,
        }

    def load_actual_results(self) -> dict | None:
        """実選挙結果を読み込み（存在しない場合はNone）"""
        if not ACTUAL_DIR.exists():
            return None

        result = {}

        # actual_results.json
        json_path = ACTUAL_DIR / "actual_results.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                result["summary"] = json.load(f)

        # district_results.csv
        csv_path = ACTUAL_DIR / "district_results.csv"
        if csv_path.exists():
            district_results = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    for key in ["winner_votes", "runner_up_votes", "margin"]:
                        if key in row and row[key]:
                            row[key] = int(row[key])
                    for key in ["turnout_rate"]:
                        if key in row and row[key]:
                            row[key] = float(row[key])
                    district_results.append(row)
            result["district_results"] = district_results

        return result if result else None
