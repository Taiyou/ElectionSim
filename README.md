# ElectionSim - 衆議院選挙AI予測ダッシュボード

複数のAIエージェントとペルソナ投票シミュレーションを活用して日本の衆議院選挙の当選予測を行うフルスタックWebアプリケーションです。

## 概要

本プロジェクトは2つのアプローチで全465議席（小選挙区289 + 比例代表176）の当選予測を行います。

1. **ペルソナ投票シミュレーション** — 15種類の有権者ペルソナ（選挙区あたり100人）を生成し、ルールベース+LLMのハイブリッドで投票行動をシミュレート
2. **マルチAI予測パイプライン** — Perplexity（ニュース）・Grok（SNS）・Claude（統合判断）の3段階分析

```
【シミュレーション】                    【マルチAI分析】
15種ペルソナ × 289選挙区                Perplexity (ニュース・世論調査)
  ↓ ルールベース投票                            ↘
  ↓ LLMスイング層処理                            → Claude (統合判定) → 予測結果
  → 選挙区・比例結果                            ↗
                                        Grok (SNS・X世論)
```

### 主な機能

| 機能 | 説明 |
|------|------|
| **ペルソナ投票シミュレーション** | 15種類の有権者類型による擬似投票（6要因モデル） |
| **マルチAI分析** | Perplexity + Grok + Claude の3段階予測パイプライン |
| **実験バージョン管理** | パラメータ・設定スナップショット付きで実験を保存・比較 |
| **マニフェスト比較** | 13政党の政策を分野別に比較表示 |
| **全465議席対応** | 小選挙区289 + 比例代表11ブロック176議席 |
| **自動予測** | 1日3回（8:00, 12:00, 20:00 JST）自動実行 |
| **地図可視化** | 都道府県別の勢力図をインタラクティブ地図で表示 |
| **YouTube・ニュース分析** | メディア報道量・動画感情分析・政党支持率追跡 |
| **予測モデル比較** | 複数手法の予測精度を比較 |

## 技術スタック

### バックエンド

| 技術 | 用途 |
|------|------|
| Python 3.12 | 言語 |
| FastAPI | Webフレームワーク |
| SQLAlchemy 2.0 (async) | ORM |
| PostgreSQL 16 / SQLite | データベース |
| APScheduler | 定期実行 |
| httpx | 非同期HTTPクライアント |
| Pydantic | バリデーション |

### フロントエンド

| 技術 | 用途 |
|------|------|
| Next.js 14 | Reactフレームワーク |
| React 18 | UI |
| TypeScript 5.6 | 言語 |
| Tailwind CSS 3.4 | スタイリング |
| Recharts | データ可視化 |
| react-simple-maps | 地図表示 |
| SWR | データフェッチ |

### インフラ

| 技術 | 用途 |
|------|------|
| Docker / Docker Compose | コンテナ管理 |
| PostgreSQL 16 | 本番DB |

## クイックスタート

### 前提条件

- Docker & Docker Compose
- [OpenRouter](https://openrouter.ai) APIキー

### 1. クローン

```bash
git clone https://github.com/Taiyou/ElectionSim.git
cd ElectionSim
```

### 2. 環境変数を設定

```bash
cp .env.example .env
```

`.env` を編集して `OPENROUTER_API_KEY` を設定してください。

### 3. 起動

```bash
docker compose up -d
```

### 4. アクセス

| サービス | URL |
|---------|-----|
| ダッシュボード | http://localhost:3000 |
| API (Swagger UI) | http://localhost:8000/docs |
| ヘルスチェック | http://localhost:8000/api/v1/health |

## ローカル開発

Docker を使わずにローカルで開発する場合:

### バックエンド

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export DATABASE_URL="sqlite+aiosqlite:///./election_ai.db"
export OPENROUTER_API_KEY="sk-or-v1-your-key"

uvicorn app.main:app --reload --port 8000
```

### フロントエンド

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
npm run dev
```

## プロジェクト構成

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI エントリーポイント
│   │   ├── config.py            # 設定管理
│   │   ├── api/                 # APIルーター
│   │   │   ├── predictions.py   #   予測パイプライン
│   │   │   ├── simulation.py    #   シミュレーション実行
│   │   │   ├── manifesto.py     #   マニフェスト比較
│   │   │   ├── districts.py     #   選挙区マスター
│   │   │   ├── news.py          #   ニュース
│   │   │   ├── youtube.py       #   YouTube分析
│   │   │   └── ...
│   │   ├── models/              # SQLAlchemy ORMモデル
│   │   ├── schemas/             # リクエスト/レスポンススキーマ
│   │   ├── services/            # ビジネスロジック
│   │   │   ├── prediction_pipeline.py  # マルチAI予測オーケストレーター
│   │   │   ├── perplexity_service.py   # ニュース分析
│   │   │   ├── grok_service.py         # SNS世論分析
│   │   │   ├── claude_service.py       # 統合判定
│   │   │   ├── openrouter_client.py    # API共通クライアント
│   │   │   ├── experiment_manager.py   # 実験バージョン管理
│   │   │   ├── experiment_comparison.py # 実験比較
│   │   │   ├── news_fetcher.py         # ニュースデータ取得
│   │   │   ├── youtube_fetcher.py      # YouTubeデータ取得
│   │   │   └── simulation/             # シミュレーションエンジン
│   │   │       ├── engine.py           #   メインエンジン
│   │   │       ├── persona_generator.py #   ペルソナ生成
│   │   │       ├── vote_calculator.py  #   投票行動計算
│   │   │       ├── result_aggregator.py #   結果集計
│   │   │       ├── validators.py       #   バリデーション
│   │   │       └── prompts.py          #   LLMプロンプト
│   │   ├── prompts/             # AIプロンプト定義
│   │   ├── db/                  # DB接続・シード
│   │   ├── scheduler/           # APSchedulerジョブ
│   │   └── data/                # マスターデータ (JSON/CSV)
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router (ページ)
│   │   │   ├── simulation/      #   シミュレーション実行UI
│   │   │   ├── manifesto/       #   マニフェスト比較
│   │   │   ├── personas/        #   ペルソナ分析
│   │   │   ├── map/             #   地図表示
│   │   │   └── ...
│   │   ├── components/          # Reactコンポーネント
│   │   ├── lib/                 # APIクライアント・定数
│   │   └── types/               # TypeScript型定義
│   ├── package.json
│   └── Dockerfile
├── persona_data/                # ペルソナ・選挙区データ
│   ├── persona_config.json      #   15種ペルソナ定義・投票要因重み
│   ├── manifesto_policies.json  #   13政党の政策データ
│   └── districts/               #   289選挙区の人口統計・政治傾向CSV
├── results/                     # シミュレーション結果
│   ├── experiments/             #   バージョン管理された実験結果
│   └── pilot/                   #   パイロット実行結果
├── scripts/                     # CLIスクリプト
├── docker-compose.yml
└── .env.example
```

## シミュレーションエンジン

ペルソナ投票シミュレーションの流れ:

```
1. ペルソナ生成 (選挙区あたり100人、15種のアーキタイプから加重抽出)
              │
2. 投票行動決定 (6要因モデル)
   ┌─ 政党忠誠度 (30%)
   ├─ 政策一致度 (25%)
   ├─ 候補者魅力 (20%)
   ├─ メディア影響 (10%)
   ├─ 地域密着度 (10%)
   └─ 戦略的投票 (5%)
              │
   ├─ 低スイング層 → ルールベース確定
   └─ 高スイング層 → LLMバッチ処理
              │
3. 選挙区集計 → 当選者・比例得票
              │
4. バリデーション (投票率・政党分布・アーキタイプ傾向)
```

## 実験バージョン管理

シミュレーション実験をバージョン管理し、パラメータ変更の影響を追跡できます。

```bash
# 実験を実行（結果+メタデータ+設定スナップショットを自動保存）
python scripts/run_experiment.py --mode pilot --seed 42 --description "ベースライン"

# 別パラメータで再実行
python scripts/run_experiment.py --mode pilot --seed 99 --description "シード変更"

# 実験一覧
python scripts/run_experiment.py --list

# 2つの実験を比較（当選者一致率・議席差分・投票率相関）
python scripts/run_experiment.py --compare sim_xxx sim_yyy

# 実選挙結果を投入し比較
python scripts/load_actual_results.py --csv actual_results.csv
python scripts/run_experiment.py --compare-actual sim_xxx

# 全実験を一括比較
python scripts/run_experiment.py --compare-all-actual
```

各実験には以下が保存されます:
- `metadata.json` — パラメータ、設定ハッシュ、投票要因重み、git commit
- `district_results.csv` / `proportional_results.csv` — 選挙区・比例結果
- `config_snapshot/` — persona_config.json, manifesto_policies.json の凍結コピー
- `validation_report.json` — バリデーション結果

詳細は [Wiki - 実験バージョン管理](../../wiki/Experiment-Versioning) を参照してください。

## AI予測パイプライン

予測は都道府県単位で並列処理（最大5件同時）されます。

```
1. マスターデータロード (47都道府県・全選挙区・候補者・13政党)
              │
2. 都道府県ごとに並列処理
   ┌──────────┴──────────┐
   │                     │
   Perplexity            Grok
   (ニュース・世論調査)   (X/SNS世論)
   │                     │
   └──────────┬──────────┘
              │
         Claude (統合分析)
         ├── 当選政党の予測
         ├── 信頼度 (high/medium/low)
         ├── 分析サマリー
         └── 候補者順位
              │
3. 比例ブロック予測 (11ブロック)
              │
4. バッチサマリー生成
```

### 使用AIモデル

| モデル | 用途 | 環境変数 |
|--------|------|---------|
| `perplexity/sonar-pro` | ニュース・世論調査分析 | `PERPLEXITY_MODEL` |
| `x-ai/grok-3` | X/SNS世論分析 | `GROK_MODEL` |
| `anthropic/claude-sonnet-4` | 統合分析・最終判定 | `CLAUDE_MODEL` |

## APIエンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| `GET` | `/api/v1/predictions/summary` | ダッシュボード用サマリー |
| `GET` | `/api/v1/predictions/latest` | 全選挙区の最新予測 |
| `GET` | `/api/v1/predictions/battleground` | 接戦区一覧 |
| `GET` | `/api/v1/predictions/district/{id}` | 選挙区詳細 |
| `GET` | `/api/v1/districts` | 選挙区マスター |
| `GET` | `/api/v1/proportional/blocks` | 比例ブロック予測 |
| `POST` | `/api/v1/simulation/run` | シミュレーション実行 |
| `POST` | `/api/v1/simulation/pilot` | パイロットシミュレーション |
| `GET` | `/api/v1/manifesto/policies` | マニフェスト一覧 |
| `GET` | `/api/v1/news/articles` | ニュース記事一覧 |
| `GET` | `/api/v1/youtube/videos` | YouTube動画一覧 |
| `GET` | `/api/v1/health` | ヘルスチェック |

詳細は [Swagger UI](http://localhost:8000/docs) または [Wiki - APIリファレンス](../../wiki/API-Reference) を参照してください。

## 画面一覧

| ページ | パス | 説明 |
|--------|------|------|
| ダッシュボード | `/` | 議席予測・接戦区・統計サマリー |
| シミュレーション | `/simulation` | ペルソナ投票シミュレーション実行・結果表示 |
| マニフェスト | `/manifesto` | 13政党の政策比較 |
| ペルソナ分析 | `/personas` | 有権者類型・投票傾向ヒートマップ |
| 地図 | `/map` | 都道府県別インタラクティブ勢力図 |
| 接戦区一覧 | `/battleground` | 信頼度が低い選挙区 |
| 選挙区詳細 | `/district/[id]` | 個別予測・候補者・履歴 |
| 比例代表 | `/proportional` | 11ブロック別議席配分 |
| ニュース | `/news` | ニュース・世論調査・報道量推移 |
| YouTube | `/youtube` | チャンネル・動画・感情分析 |
| モデル比較 | `/models` | 外部予測モデルとの比較 |

## 環境変数

| 変数名 | 必須 | デフォルト | 説明 |
|--------|:----:|-----------|------|
| `OPENROUTER_API_KEY` | **必須** | - | OpenRouter APIキー |
| `DATABASE_URL` | | `sqlite+aiosqlite:///./election_ai.db` | DB接続文字列 |
| `PERPLEXITY_MODEL` | | `perplexity/sonar-pro` | ニュース分析モデル |
| `GROK_MODEL` | | `x-ai/grok-3` | SNS分析モデル |
| `CLAUDE_MODEL` | | `anthropic/claude-sonnet-4` | 統合分析モデル |
| `YOUTUBE_API_KEY` | | - | YouTube Data API v3 キー |
| `NEWS_API_KEY` | | - | NewsAPI.org キー |
| `PARALLEL_PREFECTURES` | | `5` | 同時処理都道府県数 |
| `SCHEDULE_HOURS` | | `8,12,20` | 定期実行時刻 (JST) |
| `API_RATE_LIMIT_PER_MINUTE` | | `30` | APIレートリミット/分 |
| `MAX_RETRIES` | | `3` | リトライ回数 |

## 運用スクリプト

```bash
# シミュレーション実験（バージョン管理付き）
python scripts/run_experiment.py --mode pilot --seed 42 --description "説明"

# パイロットシミュレーション（レガシー・バージョン管理なし）
python scripts/run_pilot_simulation.py

# マルチAI予測パイプライン実行
python scripts/run_prediction.py

# 実選挙結果投入
python scripts/load_actual_results.py --csv actual_results.csv

# 選挙区マスターデータ生成
python scripts/generate_districts.py

# 失敗した都道府県を再実行
python scripts/retry_failed_prefectures.py
```

## 対象政党

| 政党名 | 略称 | 英語ID |
|--------|------|--------|
| 自由民主党 | 自民 | LDP |
| 中道改革連合 | 中道 | Chudo |
| 日本維新の会 | 維新 | Ishin |
| 国民民主党 | 国民 | DPFP |
| 日本共産党 | 共産 | JCP |
| れいわ新選組 | れいわ | Reiwa |
| 参政党 | 参政 | Sansei |
| 減税日本 | 減税 | Genzei |
| 日本保守党 | 保守 | Hoshuto |
| 社会民主党 | 社民 | SDP |
| チームみらい | みらい | Mirai |
| 諸派 | 諸派 | Minor |
| 無所属 | 無所属 | Independent |

## ドキュメント

詳細なドキュメントは [GitHub Wiki](../../wiki) を参照してください。

- [システムアーキテクチャ](../../wiki/Architecture)
- [バックエンド詳細](../../wiki/Backend)
- [フロントエンド詳細](../../wiki/Frontend)
- [AI予測パイプライン](../../wiki/AI-Pipeline)
- [データ・ペルソナ](../../wiki/Data-and-Personas)
- [実験バージョン管理](../../wiki/Experiment-Versioning)
- [APIリファレンス](../../wiki/API-Reference)
- [セットアップガイド](../../wiki/Setup-Guide)

## ライセンス

MIT
