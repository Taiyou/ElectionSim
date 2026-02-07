"""
実験バージョン管理スクリプト

シミュレーションの実験設計・設定・結果・ソースコードを
バージョン付きディレクトリに保存する。

使い方:
  python scripts/save_experiment.py v2_llm_hybrid "LLMハイブリッド実行（50選挙区）"
  python scripts/save_experiment.py v3_full_run "全289選挙区フル実行" --results-dir results/full
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = BASE_DIR / "experiments"

# 保存対象のソースファイル
SOURCE_FILES = [
    "backend/app/services/simulation/engine.py",
    "backend/app/services/simulation/persona_generator.py",
    "backend/app/services/simulation/vote_calculator.py",
    "backend/app/services/simulation/result_aggregator.py",
    "backend/app/services/simulation/validators.py",
    "backend/app/services/simulation/prompts.py",
    "scripts/run_pilot_simulation.py",
]

# 保存対象の設定ファイル
CONFIG_FILES = [
    "persona_data/persona_config.json",
    "persona_data/manifesto_policies.json",
]


def save_experiment(
    version: str,
    description: str,
    results_dir: str = "results/pilot",
    extra_notes: str = "",
):
    """実験のスナップショットを保存"""

    exp_dir = EXPERIMENTS_DIR / version
    if exp_dir.exists():
        print(f"WARNING: {exp_dir} already exists. Overwriting.")

    # ディレクトリ作成
    (exp_dir / "results").mkdir(parents=True, exist_ok=True)
    (exp_dir / "config").mkdir(parents=True, exist_ok=True)
    (exp_dir / "source_snapshot").mkdir(parents=True, exist_ok=True)

    # 1. 結果ファイルのコピー
    src_results = BASE_DIR / results_dir
    if src_results.exists():
        results_copied = []
        for f in src_results.iterdir():
            if f.is_file():
                shutil.copy2(f, exp_dir / "results" / f.name)
                results_copied.append(f.name)
        print(f"Results: {len(results_copied)} files copied from {results_dir}")
    else:
        print(f"WARNING: Results directory not found: {results_dir}")
        results_copied = []

    # 2. 設定ファイルのコピー
    config_copied = []
    for rel_path in CONFIG_FILES:
        src = BASE_DIR / rel_path
        if src.exists():
            shutil.copy2(src, exp_dir / "config" / src.name)
            config_copied.append(src.name)
    print(f"Config: {len(config_copied)} files copied")

    # 3. ソースファイルのコピー
    source_copied = []
    for rel_path in SOURCE_FILES:
        src = BASE_DIR / rel_path
        if src.exists():
            shutil.copy2(src, exp_dir / "source_snapshot" / src.name)
            source_copied.append(src.name)
    print(f"Source: {len(source_copied)} files copied")

    # 4. 結果サマリの読み込み（あれば）
    summary_data = {}
    summary_path = exp_dir / "results" / "summary.json"
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)

    # 5. experiment.json の生成
    experiment_meta = {
        "version": version,
        "title": description,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "status": "completed",
        "description": description,
        "notes": extra_notes,
        "results_summary": summary_data,
        "files": {
            "results": [f"results/{f}" for f in results_copied],
            "config": [f"config/{f}" for f in config_copied],
            "source_snapshot": [f"source_snapshot/{f}" for f in source_copied],
        },
    }

    meta_path = exp_dir / "experiment.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(experiment_meta, f, ensure_ascii=False, indent=2)

    print(f"\nExperiment saved: {exp_dir}")
    print(f"Metadata: {meta_path}")

    return exp_dir


def list_experiments():
    """保存済み実験一覧を表示"""
    if not EXPERIMENTS_DIR.exists():
        print("No experiments directory found.")
        return

    experiments = []
    for d in sorted(EXPERIMENTS_DIR.iterdir()):
        if d.is_dir():
            meta_path = d / "experiment.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                experiments.append(meta)

    if not experiments:
        print("No experiments found.")
        return

    print(f"{'Version':<30} {'Date':<12} {'Status':<12} {'Title'}")
    print("-" * 90)
    for exp in experiments:
        print(
            f"{exp.get('version', '?'):<30} "
            f"{exp.get('date', '?'):<12} "
            f"{exp.get('status', '?'):<12} "
            f"{exp.get('title', '?')}"
        )


def main():
    parser = argparse.ArgumentParser(description="実験バージョン管理ツール")
    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # save
    save_parser = subparsers.add_parser("save", help="実験を保存")
    save_parser.add_argument("version", help="バージョン名 (e.g. v2_llm_hybrid)")
    save_parser.add_argument("description", help="実験の説明")
    save_parser.add_argument(
        "--results-dir", default="results/pilot",
        help="結果ディレクトリのパス (default: results/pilot)"
    )
    save_parser.add_argument("--notes", default="", help="追加メモ")

    # list
    subparsers.add_parser("list", help="保存済み実験一覧")

    args = parser.parse_args()

    if args.command == "save":
        save_experiment(args.version, args.description, args.results_dir, args.notes)
    elif args.command == "list":
        list_experiments()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
