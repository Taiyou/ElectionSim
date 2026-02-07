# Election AI - 衆議院選挙AI予測ダッシュボード

複数のAIエージェントを活用して日本の衆議院選挙の当選予測を行うフルスタックWebアプリケーションです。

## 概要

3つのAIモデル（Perplexity・Grok・Claude）を [OpenRouter](https://openrouter.ai) API経由で連携させ、全465議席（小選挙区289 + 比例代表176）の当選予測を自動的に生成・更新します。

```
Perplexity (ニュース・世論調査分析)
         ↘
           → Claude (統合分析・最終判定) → 予測結果
         ↗
Grok (SNS・X世論分析)
```

### 主な機能

- **マルチAIエージェント分析** - ニュース分析、SNS世論分析、統合判定の3段階パイプライン
- **全選挙区カバー** - 47都道府県の全小選挙区 + 11比例ブロックに対応
- **リアルタイムダッシュボード** - 議席予測、接戦区、信頼度分布をビジュアル表示
- **自動定期更新** - 1日3回（8時・12時・20時 JST）自動で予測を更新
- **予測履歴追跡** - 予測の変遷を時系列で記録・表示

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
| tenacity | リトライロジック |
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
git clone https://github.com/Taiyou/replication-horiemonAI.git
cd replication-horiemonAI
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
│   │   ├── models/              # SQLAlchemy ORMモデル
│   │   ├── schemas/             # リクエスト/レスポンススキーマ
│   │   ├── services/            # ビジネスロジック
│   │   │   ├── prediction_pipeline.py  # 予測オーケストレーター
│   │   │   ├── perplexity_service.py   # ニュース分析
│   │   │   ├── grok_service.py         # SNS世論分析
│   │   │   ├── claude_service.py       # 統合判定
│   │   │   └── openrouter_client.py    # API共通クライアント
│   │   ├── prompts/             # AIプロンプト定義
│   │   ├── db/                  # DB接続・シード
│   │   ├── scheduler/           # APSchedulerジョブ
│   │   └── data/                # マスターデータ (JSON)
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router (ページ)
│   │   ├── components/          # Reactコンポーネント
│   │   ├── lib/                 # APIクライアント・定数
│   │   └── types/               # TypeScript型定義
│   ├── package.json
│   └── Dockerfile
├── scripts/                     # 運用スクリプト
├── docker-compose.yml
└── .env.example
```

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
| `GET` | `/api/v1/health` | ヘルスチェック |

詳細は [Swagger UI](http://localhost:8000/docs) または [Wiki - APIリファレンス](../../wiki/API-Reference) を参照してください。

## 環境変数

| 変数名 | 必須 | デフォルト | 説明 |
|--------|:----:|-----------|------|
| `OPENROUTER_API_KEY` | **必須** | - | OpenRouter APIキー |
| `DATABASE_URL` | | `sqlite+aiosqlite:///./election_ai.db` | DB接続文字列 |
| `PERPLEXITY_MODEL` | | `perplexity/sonar-pro` | ニュース分析モデル |
| `GROK_MODEL` | | `x-ai/grok-3` | SNS分析モデル |
| `CLAUDE_MODEL` | | `anthropic/claude-sonnet-4` | 統合分析モデル |
| `PARALLEL_PREFECTURES` | | `5` | 同時処理都道府県数 |
| `SCHEDULE_HOURS` | | `8,12,20` | 定期実行時刻 (JST) |
| `API_RATE_LIMIT_PER_MINUTE` | | `30` | APIレートリミット/分 |
| `MAX_RETRIES` | | `3` | リトライ回数 |

## 運用スクリプト

```bash
# 手動で予測を実行
python scripts/run_prediction.py

# 選挙区マスターデータを生成
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
| 減税日本 | 減ゆ | Genzei |
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
- [APIリファレンス](../../wiki/API-Reference)
- [セットアップガイド](../../wiki/Setup-Guide)

## ライセンス

MIT
