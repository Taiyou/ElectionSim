#!/usr/bin/env python3
"""
実験アーカイブ作成スクリプト
============================
全実験データ・マスターデータ・コード・環境情報を統合し、
再現可能なアーカイブフォルダを生成する。

使用方法:
    python scripts/create_archive.py
    python scripts/create_archive.py --output-dir /path/to/output
    python scripts/create_archive.py --tag "pre_election"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# アーカイブに含めるマスターデータ
MASTER_DATA_FILES = [
    # 候補者・政党
    "backend/app/data/candidates.csv",
    "backend/app/data/parties.json",
    "backend/app/data/prefectures.json",
    "backend/app/data/proportional_blocks.json",
    "backend/app/data/districts_sample.json",
    # ペルソナ設定
    "persona_data/persona_config.json",
    "persona_data/voter_profiles.json",
    "persona_data/political_tendencies.json",
    "persona_data/socioeconomic_indicators.json",
    "persona_data/regional_issues.json",
    "persona_data/prefecture_demographics.json",
    "persona_data/manifesto_policies.json",
    "persona_data/data_sources.csv",
    # 選挙区ペルソナ分布
    "persona_data/districts/all_districts_persona_data.csv",
    "persona_data/districts/districts_demographics.csv",
    "persona_data/districts/districts_socioeconomic.csv",
    "persona_data/districts/districts_political_tendencies.csv",
    "persona_data/districts/districts_voter_profiles.csv",
    "persona_data/districts/districts_regional_issues.csv",
]

# ソースコード（バックエンド主要ファイル）
SOURCE_CODE_PATTERNS = {
    "backend/app/services/simulation/": [
        "engine.py",
        "persona_generator.py",
        "vote_calculator.py",
        "llm_voter.py",
        "result_aggregator.py",
        "prompts.py",
        "validators.py",
    ],
    "backend/app/api/": [
        "simulation.py",
    ],
    "backend/app/schemas/": [
        "simulation.py",
    ],
    "backend/app/services/": [
        "experiment_manager.py",
        "experiment_comparison.py",
        "prediction_pipeline.py",
    ],
    "scripts/": None,  # 全ファイル
}

# 環境ファイル
ENV_FILES = [
    "backend/pyproject.toml",
    "frontend/package.json",
    ".env.example",
    "docker-compose.yml",
]


def file_hash(filepath: Path) -> str:
    """SHA-256ハッシュを計算"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_git_info() -> dict:
    """Gitリポジトリ情報を取得"""
    info = {}
    try:
        info["commit_hash"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
        info["commit_message"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], cwd=PROJECT_ROOT, text=True
        ).strip()
        info["commit_date"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%ci"], cwd=PROJECT_ROOT, text=True
        ).strip()
        # 未コミット変更の有無
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True
        ).strip()
        info["has_uncommitted_changes"] = len(status) > 0
        if status:
            info["uncommitted_files"] = status.split("\n")
    except Exception as e:
        info["error"] = str(e)
    return info


def get_system_info() -> dict:
    """システム情報を取得"""
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "archive_created_at": datetime.now().isoformat(),
    }


def copy_file(src: Path, dst: Path):
    """ファイルをコピー（親ディレクトリも作成）"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_dir(src: Path, dst: Path):
    """ディレクトリを再帰コピー"""
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def collect_file_manifest(base_dir: Path) -> list[dict]:
    """アーカイブ内の全ファイルのマニフェストを生成"""
    manifest = []
    for filepath in sorted(base_dir.rglob("*")):
        if filepath.is_file():
            rel = filepath.relative_to(base_dir)
            manifest.append({
                "path": str(rel),
                "size_bytes": filepath.stat().st_size,
                "sha256": file_hash(filepath),
                "modified": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
            })
    return manifest


def parse_experiment_metadata(exp_dir: Path) -> dict:
    """実験ディレクトリからメタデータを抽出"""
    meta = {"directory": exp_dir.name}

    # experiment.json (versioned experiments)
    exp_json = exp_dir / "experiment.json"
    if exp_json.exists():
        with open(exp_json) as f:
            meta["experiment_config"] = json.load(f)

    # metadata.json (results experiments)
    meta_json = exp_dir / "metadata.json"
    if meta_json.exists():
        with open(meta_json) as f:
            meta["metadata"] = json.load(f)

    # summary.json
    summary_json = exp_dir / "summary.json"
    if summary_json.exists():
        with open(summary_json) as f:
            meta["summary"] = json.load(f)

    # ファイル一覧
    meta["files"] = [
        str(f.relative_to(exp_dir)) for f in sorted(exp_dir.rglob("*")) if f.is_file()
    ]

    return meta


def build_data_sources_index(project_root: Path) -> list[dict]:
    """外部データソースの参照情報をインデックス化"""
    csv_path = project_root / "persona_data" / "data_sources.csv"
    if not csv_path.exists():
        return []

    import csv
    sources = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sources.append({
                "category": row.get("データカテゴリ", ""),
                "file": row.get("ファイル名", ""),
                "field": row.get("データ項目", ""),
                "source": row.get("主要出典", ""),
                "organization": row.get("出典機関", ""),
                "url": row.get("出典URL", ""),
                "year": row.get("データ基準年", ""),
                "granularity": row.get("粒度", ""),
                "notes": row.get("備考", ""),
            })
    return sources


def create_archive(output_base: Path = None, tag: str = None):
    """アーカイブを作成"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"archive_{timestamp}"
    if tag:
        archive_name = f"archive_{tag}_{timestamp}"

    if output_base is None:
        output_base = PROJECT_ROOT / "archive"

    archive_dir = output_base / archive_name
    archive_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== アーカイブ作成開始 ===")
    print(f"出力先: {archive_dir}")
    print()

    # ========================================
    # 1. マスターデータのコピー
    # ========================================
    print("[1/7] マスターデータをコピー中...")
    master_dir = archive_dir / "master_data"
    master_count = 0
    for rel_path in MASTER_DATA_FILES:
        src = PROJECT_ROOT / rel_path
        if src.exists():
            # ファイル名のみでフラット保存（サブディレクトリの場合はパスを保持）
            dst_name = Path(rel_path).name
            # 重複回避のためカテゴリ別サブフォルダ
            if "districts/" in rel_path:
                dst = master_dir / "districts" / dst_name
            elif "backend/app/data/" in rel_path:
                dst = master_dir / "candidates_parties" / dst_name
            else:
                dst = master_dir / "persona" / dst_name
            copy_file(src, dst)
            master_count += 1
        else:
            print(f"  [警告] ファイルが見つかりません: {rel_path}")
    print(f"  → {master_count} ファイルをコピー")

    # ========================================
    # 2. 実験スナップショットのコピー
    # ========================================
    print("[2/7] 実験スナップショットをコピー中...")
    exp_src = PROJECT_ROOT / "experiments"
    exp_dst = archive_dir / "experiments"
    if exp_src.exists():
        copy_dir(exp_src, exp_dst)
        exp_count = sum(1 for _ in exp_dst.rglob("*") if _.is_file())
        print(f"  → {exp_count} ファイルをコピー")

    # ========================================
    # 3. 実験結果のコピー
    # ========================================
    print("[3/7] 実験結果をコピー中...")
    results_src = PROJECT_ROOT / "results"
    results_dst = archive_dir / "results"
    if results_src.exists():
        copy_dir(results_src, results_dst)
        res_count = sum(1 for _ in results_dst.rglob("*") if _.is_file())
        print(f"  → {res_count} ファイルをコピー")

    # ========================================
    # 4. ソースコードのコピー
    # ========================================
    print("[4/7] ソースコードをコピー中...")
    code_dir = archive_dir / "source_code"
    code_count = 0
    for dir_prefix, files in SOURCE_CODE_PATTERNS.items():
        src_dir = PROJECT_ROOT / dir_prefix
        if not src_dir.exists():
            continue
        if files is None:
            # 全 .py ファイル
            for py_file in src_dir.glob("*.py"):
                dst = code_dir / dir_prefix / py_file.name
                copy_file(py_file, dst)
                code_count += 1
        else:
            for fname in files:
                src = src_dir / fname
                if src.exists():
                    dst = code_dir / dir_prefix / fname
                    copy_file(src, dst)
                    code_count += 1

    # git情報も保存
    git_info = get_git_info()
    git_info_path = code_dir / "git_info.json"
    git_info_path.parent.mkdir(parents=True, exist_ok=True)
    with open(git_info_path, "w", encoding="utf-8") as f:
        json.dump(git_info, f, indent=2, ensure_ascii=False)
    code_count += 1
    print(f"  → {code_count} ファイルをコピー")

    # ========================================
    # 5. 環境情報の保存
    # ========================================
    print("[5/7] 環境情報を保存中...")
    env_dir = archive_dir / "environment"
    env_dir.mkdir(parents=True, exist_ok=True)
    env_count = 0

    for rel_path in ENV_FILES:
        src = PROJECT_ROOT / rel_path
        if src.exists():
            copy_file(src, env_dir / Path(rel_path).name)
            env_count += 1

    # システム情報
    sys_info = get_system_info()
    with open(env_dir / "system_info.json", "w", encoding="utf-8") as f:
        json.dump(sys_info, f, indent=2, ensure_ascii=False)
    env_count += 1

    # .envから機密情報を除去して保存
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file) as f:
            lines = f.readlines()
        sanitized = []
        for line in lines:
            line_stripped = line.strip()
            if "=" in line_stripped and not line_stripped.startswith("#"):
                key = line_stripped.split("=", 1)[0]
                if any(secret in key.upper() for secret in ["KEY", "SECRET", "TOKEN", "PASSWORD"]):
                    sanitized.append(f"{key}=<REDACTED>\n")
                else:
                    sanitized.append(line)
            else:
                sanitized.append(line)
        with open(env_dir / "env_sanitized.txt", "w") as f:
            f.writelines(sanitized)
        env_count += 1

    print(f"  → {env_count} ファイルを保存")

    # ========================================
    # 6. 外部データソース参照情報
    # ========================================
    print("[6/7] データソース参照情報を整理中...")
    ds_dir = archive_dir / "data_sources"
    ds_dir.mkdir(parents=True, exist_ok=True)

    # data_sources.csvをコピー
    ds_csv = PROJECT_ROOT / "persona_data" / "data_sources.csv"
    if ds_csv.exists():
        copy_file(ds_csv, ds_dir / "data_sources.csv")

    # URLインデックスを生成
    sources = build_data_sources_index(PROJECT_ROOT)
    with open(ds_dir / "source_urls.json", "w", encoding="utf-8") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)

    # YouTubeデータ
    yt_src = PROJECT_ROOT / "persona_data" / "youtube"
    if yt_src.exists():
        copy_dir(yt_src, ds_dir / "youtube")

    print(f"  → データソース情報を保存")

    # ========================================
    # 7. インデックスファイルの生成
    # ========================================
    print("[7/7] インデックスファイルを生成中...")

    # 実験メタデータの収集
    experiment_index = []

    # experiments/ ディレクトリ内
    if exp_dst.exists():
        for d in sorted(exp_dst.iterdir()):
            if d.is_dir():
                meta = parse_experiment_metadata(d)
                experiment_index.append(meta)

    # results/experiments/ ディレクトリ内
    results_exp_dir = results_dst / "experiments"
    if results_exp_dir.exists():
        for d in sorted(results_exp_dir.iterdir()):
            if d.is_dir():
                meta = parse_experiment_metadata(d)
                meta["type"] = "result"
                experiment_index.append(meta)

    # ファイルマニフェスト
    manifest = collect_file_manifest(archive_dir)

    # 統計
    total_size = sum(f["size_bytes"] for f in manifest)
    total_files = len(manifest)

    index = {
        "archive_info": {
            "name": archive_name,
            "created_at": datetime.now().isoformat(),
            "tag": tag,
            "project": "ElectionSim - 衆議院選挙AI予測",
            "project_root": str(PROJECT_ROOT),
        },
        "git": git_info,
        "system": sys_info,
        "statistics": {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        },
        "experiments": experiment_index,
        "data_sources": sources,
        "file_manifest": manifest,
    }

    with open(archive_dir / "INDEX.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print()
    print(f"=== アーカイブ作成完了 ===")
    print(f"場所: {archive_dir}")
    print(f"ファイル数: {total_files}")
    print(f"合計サイズ: {round(total_size / (1024 * 1024), 2)} MB")
    print()

    return archive_dir


def create_reproduction_guide(archive_dir: Path):
    """再現手順書を生成"""
    guide_path = archive_dir / "REPRODUCTION_GUIDE.md"

    # INDEX.jsonから情報を読み取る
    index_path = archive_dir / "INDEX.json"
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    git_info = index.get("git", {})
    experiments = index.get("experiments", [])

    # 実験一覧テーブル
    exp_table_rows = []
    for exp in experiments:
        name = exp.get("directory", "")
        exp_config = exp.get("experiment_config", {})
        metadata = exp.get("metadata", {})

        if exp_config:
            method = exp_config.get("method", "")
            districts = exp_config.get("districts", "")
            seed = exp_config.get("seed", "")
        elif metadata:
            params = metadata.get("parameters", {})
            method = metadata.get("method", params.get("method", ""))
            districts = params.get("num_districts", "")
            seed = params.get("seed", "")
        else:
            method = districts = seed = ""

        exp_table_rows.append(f"| {name} | {method} | {districts} | {seed} |")

    exp_table = "\n".join(exp_table_rows) if exp_table_rows else "| (データなし) | | | |"

    guide_content = f"""# 実験再現ガイド (Reproduction Guide)

## アーカイブ情報

- **作成日時**: {index['archive_info']['created_at']}
- **タグ**: {index['archive_info'].get('tag', 'なし')}
- **Gitコミット**: `{git_info.get('commit_hash', 'N/A')}`
- **ブランチ**: `{git_info.get('branch', 'N/A')}`
- **未コミット変更**: {'あり' if git_info.get('has_uncommitted_changes') else 'なし'}

## フォルダ構成

```
{archive_dir.name}/
├── INDEX.json                  # 全体インデックス（実験一覧・ファイルハッシュ・データソース）
├── REPRODUCTION_GUIDE.md       # 本ファイル
├── master_data/                # 全実験共通マスターデータ
│   ├── candidates_parties/     # 候補者・政党・選挙区データ
│   ├── persona/                # ペルソナ設定・地域データ
│   └── districts/              # 選挙区別ペルソナ分布
├── experiments/                # 実験バージョン管理スナップショット
│   ├── experiment_log.md       # 実験ジャーナル
│   ├── v1_pilot_rule_based/    # Phase 1: パイロット
│   ├── v2_full_289_rule_based/ # Phase 1: 全区
│   ├── v3a_policy_focused/     # Phase 1: 政策重視
│   ├── v3b_anti_establishment/ # Phase 1: 反既成
│   ├── v3c_high_turnout/       # Phase 1: 高投票率
│   └── v4a_llm_pilot/          # Phase 2: LLMパイロット
├── results/                    # 実験結果データ
│   ├── experiments/            # 各実験の結果ファイル
│   └── aggregated/             # マルチシード集計結果
├── source_code/                # 実行時のソースコード
│   ├── backend/                # バックエンド主要コード
│   ├── scripts/                # 実験実行スクリプト
│   └── git_info.json           # Gitリポジトリ情報
├── environment/                # 環境・依存情報
│   ├── pyproject.toml          # Python依存パッケージ
│   ├── package.json            # Node.js依存パッケージ
│   ├── env_sanitized.txt       # 環境変数（APIキー除去済）
│   ├── docker-compose.yml      # コンテナ構成
│   └── system_info.json        # 実行環境情報
└── data_sources/               # 外部データソース参照
    ├── data_sources.csv        # 全データ項目の出典一覧
    ├── source_urls.json        # URL付きインデックス
    └── youtube/                # YouTube取得データ
```

## 再現手順

### 前提条件

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose（本番環境の場合）

### Step 1: 環境セットアップ

```bash
# リポジトリをクローン
git clone <repository_url>
cd replication-horiemonAI

# 特定コミットにチェックアウト（完全再現の場合）
git checkout {git_info.get('commit_hash', '<commit_hash>')}

# Python環境
cd backend
pip install -e .

# .envを設定
cp ../.env.example .env
# APIキーを設定（env_sanitized.txtのキー名を参照）
```

### Step 2: マスターデータの配置

アーカイブの `master_data/` 内のファイルを以下の場所にコピー:

```bash
# 候補者・政党データ
cp master_data/candidates_parties/* backend/app/data/

# ペルソナ設定
cp master_data/persona/* persona_data/

# 選挙区ペルソナ分布
cp master_data/districts/* persona_data/districts/
```

### Step 3: 実験の再実行

#### Phase 1: ルールベース実験

```bash
# v1: パイロット（10選挙区）
python scripts/run_pilot_simulation.py

# v2: 全289選挙区・5シード
python scripts/run_full_simulation.py

# v3: パラメータバリアント
python scripts/run_v3_experiments.py
```

#### Phase 2: LLMペルソナ実験

```bash
# v4: LLMペルソナ投票（要OpenRouter APIキー）
python scripts/run_v4_llm_persona.py
```

### Step 4: 結果の検証

アーカイブの `results/` 内のファイルと新規実行結果を比較:

```bash
# 結果CSVの比較
diff results/experiments/<experiment_id>/district_results.csv \\
     archive/<archive_name>/results/experiments/<experiment_id>/district_results.csv
```

**注意**: LLM実験（v4以降）は非決定的であるため、結果は完全には一致しません。
ルールベース実験（v1-v3）は同一シードで決定的に再現可能です。

## 実験一覧

| 実験名 | 方式 | 選挙区数 | シード |
|--------|------|----------|--------|
{exp_table}

## データソース

全データの出典は `data_sources/data_sources.csv` に記録されています。
主な出典:
- 総務省統計局: 国勢調査、労働力調査
- 総務省選挙部: 過去の選挙結果
- 各政党: マニフェスト・政策
- 厚生労働省: 賃金統計

詳細なURLリストは `data_sources/source_urls.json` を参照してください。

## ファイル整合性の検証

`INDEX.json` の `file_manifest` に全ファイルのSHA-256ハッシュが記録されています。

```python
import hashlib, json

with open("INDEX.json") as f:
    index = json.load(f)

for entry in index["file_manifest"]:
    path = entry["path"]
    expected = entry["sha256"]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    actual = h.hexdigest()
    status = "OK" if actual == expected else "MISMATCH"
    if status != "OK":
        print(f"[{{status}}] {{path}}")
```

## 注意事項

1. **APIキー**: `environment/env_sanitized.txt` のキー名を参照し、自分のAPIキーを設定してください
2. **LLM実験の非決定性**: Claude等のLLMは同一入力でも異なる出力を返すため、v4以降の結果は参考値です
3. **ルールベースの決定性**: v1-v3はシード固定で完全に再現可能です
4. **データ基準年**: 多くのデータは2020-2024年の統計に基づいています（`data_sources.csv`参照）
"""

    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)

    print(f"再現手順書を生成: {guide_path}")


def main():
    parser = argparse.ArgumentParser(description="実験アーカイブを作成")
    parser.add_argument("--output-dir", type=str, help="出力先ディレクトリ")
    parser.add_argument("--tag", type=str, help="アーカイブのタグ（例: pre_election）")
    args = parser.parse_args()

    output_base = Path(args.output_dir) if args.output_dir else None

    archive_dir = create_archive(output_base=output_base, tag=args.tag)
    create_reproduction_guide(archive_dir)

    print()
    print("全ての処理が完了しました。")
    print(f"アーカイブ: {archive_dir}")
    print(f"インデックス: {archive_dir / 'INDEX.json'}")
    print(f"再現手順書: {archive_dir / 'REPRODUCTION_GUIDE.md'}")


if __name__ == "__main__":
    main()
