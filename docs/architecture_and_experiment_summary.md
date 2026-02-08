# ElectionSim: LLMペルソナベース選挙シミュレーション

## プロジェクトアーキテクチャ・実験サマリードキュメント

---

## 目次

1. [全体のアーキテクチャ構築](#1-全体のアーキテクチャ構築)
2. [実験の並列処理](#2-実験の並列処理)
3. [実験管理](#3-実験管理)
4. [モデル管理](#4-モデル管理)
5. [既存データの整理](#5-既存データの整理)
6. [実験条件の整理](#6-実験条件の整理)
7. [実験結果の比較ポイント](#7-実験結果の比較ポイント)
8. [改善ポイントの列挙](#8-改善ポイントの列挙)
9. [先行研究の列挙と技術ポイントの比較](#9-先行研究の列挙と技術ポイントの比較)
10. [付録](#付録)

---

## 1. 全体のアーキテクチャ構築

### 1.1 システム概要

2026年2月8日投開票の衆議院選挙（289小選挙区 + 11比例ブロック = 465議席）を対象に、ペルソナベースの投票行動シミュレーションを行うフルスタックアプリケーション。ルールベースの6要因モデルとLLM（Claude Sonnet 4）によるハイブリッド投票シミュレーション、マルチAI予測パイプライン、リアルタイム可視化ダッシュボードを統合している。

```
┌──────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 14)                     │
│  Dashboard / Simulation UI / Charts / Comparison / Map        │
│  14 pages, 17 chart components, API client (SWR + fetch)      │
└────────────────────────────┬─────────────────────────────────┘
                             │ HTTP REST (fetch / SWR)
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                          │
│  /api/v1  ── 11 routers (simulation, predictions, youtube...) │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Services Layer                                           │  │
│  │  SimulationEngine ── PersonaGenerator                    │  │
│  │                   ── VoteCalculator (6-factor)            │  │
│  │                   ── LLMVoter (OpenRouter)                │  │
│  │                   ── ResultAggregator                     │  │
│  │  ExperimentManager ── ExperimentComparison                │  │
│  │  PredictionPipeline (Perplexity → Grok → Claude)         │  │
│  │  MemoryStore (SQLite 3-layer)                             │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────┬──────────────────────────┬───────────────────────────┘
        │                          │
        ▼                          ▼
┌───────────────┐    ┌───────────────────────────────────┐
│  PostgreSQL   │    │       External APIs                │
│  (Docker)     │    │  OpenRouter (Claude Sonnet 4)      │
│  election_ai  │    │  YouTube Data API                  │
│               │    │  NewsAPI                            │
└───────────────┘    └───────────────────────────────────┘
```

### 1.2 技術スタック

| レイヤー | 技術 | バージョン/詳細 |
|---------|------|----------------|
| Frontend | Next.js | 14 (App Router) |
| Frontend | React | 18 |
| Frontend | TypeScript | 5.6 (strict mode) |
| Frontend | Tailwind CSS | 3.4 |
| Frontend | Recharts | チャートライブラリ |
| Frontend | SWR | データフェッチ |
| Backend | FastAPI | async対応 |
| Backend | SQLAlchemy | 2.0 (async ORM) |
| Backend | Pydantic | v2 (Settings, Schemas) |
| Backend | httpx | AsyncClient (LLM呼び出し) |
| Database | PostgreSQL | 16-alpine (Docker) |
| Database | SQLite | 開発用 + メモリシステム (v10b) |
| LLM | OpenRouter API | Claude Sonnet 4 (`claude-sonnet-4-20250514`) |
| Infra | Docker Compose | 3サービス (db, backend, frontend) |
| Task Scheduler | APScheduler | 定期予測パイプライン (8:00/12:00/20:00 JST) |

### 1.3 ディレクトリ構成

```
replication-horiemonAI/
├── backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI エントリポイント
│   │   ├── config.py                        # Pydantic Settings
│   │   ├── api/                             # APIルーター (11個)
│   │   │   ├── router.py                    # ルーター集約
│   │   │   ├── simulation.py                # /simulation エンドポイント
│   │   │   ├── predictions.py               # /predictions エンドポイント
│   │   │   ├── districts.py, candidates.py, parties.py
│   │   │   ├── proportional.py              # 比例代表
│   │   │   ├── youtube.py, news.py          # メディアデータ
│   │   │   ├── personas.py, manifesto.py
│   │   │   ├── data_fetch.py                # データ取り込み
│   │   │   └── health.py, prompts.py
│   │   ├── db/                              # DB設定・シード
│   │   │   ├── session.py                   # async engine + session
│   │   │   ├── seed.py                      # 初期データ投入
│   │   │   └── seed_youtube_news.py         # YouTube/ニュースシード
│   │   ├── models/                          # SQLAlchemy ORM
│   │   │   ├── district.py, candidate.py, party.py
│   │   │   ├── prediction.py, prediction_history.py
│   │   │   ├── youtube.py, news.py
│   │   │   └── proportional.py
│   │   ├── schemas/                         # Pydantic スキーマ
│   │   │   ├── simulation.py                # SimulationRequest/Response
│   │   │   ├── prediction.py, district.py, candidate.py
│   │   │   ├── youtube.py, news.py
│   │   │   └── proportional.py, manifesto.py
│   │   ├── services/                        # ビジネスロジック
│   │   │   ├── simulation/                  # コアシミュレーション
│   │   │   │   ├── engine.py                # SimulationEngine (メイン)
│   │   │   │   ├── persona_generator.py     # アーキタイプ型ペルソナ生成
│   │   │   │   ├── demographic_persona_generator.py  # 人口統計型
│   │   │   │   ├── vote_calculator.py       # 6要因投票モデル
│   │   │   │   ├── llm_voter.py             # LLM投票 (OpenRouter)
│   │   │   │   ├── prompts.py               # プロンプトテンプレート
│   │   │   │   ├── result_aggregator.py     # 結果集計
│   │   │   │   ├── validators.py            # バリデーション
│   │   │   │   └── memory/                  # メモリシステム (v10b)
│   │   │   │       ├── store.py             # 3層SQLiteストア
│   │   │   │       └── memory_llm_voter.py  # メモリ付きLLM投票
│   │   │   ├── experiment_manager.py        # 実験ライフサイクル管理
│   │   │   ├── experiment_comparison.py     # 実験比較
│   │   │   ├── prediction_pipeline.py       # 3段階AI予測
│   │   │   ├── claude_service.py            # Claude API呼び出し
│   │   │   ├── grok_service.py              # Grok API呼び出し
│   │   │   └── perplexity_service.py        # Perplexity API呼び出し
│   │   ├── data/                            # 静的データ
│   │   │   ├── parties.json                 # 13政党マスタ
│   │   │   ├── districts_sample.json        # 289選挙区
│   │   │   ├── prefectures.json             # 47都道府県
│   │   │   └── proportional_blocks.json     # 11比例ブロック
│   │   ├── utils/                           # ユーティリティ
│   │   └── scheduler/                       # 定期実行ジョブ
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── app/                             # Next.js App Router (14ページ)
│       ├── components/                      # React コンポーネント
│       │   ├── charts/                      # 17種のチャート
│       │   ├── layout/                      # Header, Footer
│       │   ├── prediction/                  # 予測カード
│       │   └── models/                      # モデル詳細
│       ├── lib/                             # api-client.ts, constants.ts
│       └── types/                           # TypeScript型定義
├── persona_data/                            # ペルソナ設定データ
│   ├── districts/                           # 選挙区別ペルソナ分布
│   ├── youtube/                             # YouTube CSV
│   ├── persona_config.json                  # 15アーキタイプ定義
│   ├── manifesto_policies.json              # マニフェスト・政策
│   ├── past_elections.json                  # 過去選挙結果
│   └── economic_context.json                # 経済指標
├── scripts/                                 # 実験スクリプト
├── results/experiments/                     # 実験結果格納
├── experiments/                             # 実験設計ドキュメント
├── memory/                                  # メモリDB (agent_memory.db)
├── docker-compose.yml                       # Docker Compose定義
└── .env                                     # 環境変数
```

### 1.4 バックエンドアーキテクチャ

#### 1.4.1 APIレイヤー (11ルーター)

| ルーター | エンドポイント | 主要機能 |
|---------|-------------|---------|
| `simulation.py` | POST /simulation/run, /pilot | シミュレーション実行 |
| | GET /simulation/experiments | 実験一覧 |
| | POST /simulation/compare | 2実験比較 |
| `predictions.py` | GET /predictions/summary, /latest | 予測結果取得 |
| | GET /predictions/battleground | 接戦区分析 |
| `districts.py` | GET /districts, /districts/{id} | 選挙区マスタ |
| `candidates.py` | GET /candidates | 候補者データ |
| `parties.py` | GET /parties | 政党マスタ |
| `proportional.py` | GET /proportional/blocks | 比例ブロック |
| `youtube.py` | GET /youtube/summary | YouTube分析 |
| `news.py` | GET /news/summary | ニュース分析 |
| `data_fetch.py` | POST /data-fetch/youtube | データ取り込み |
| `personas.py` | GET /personas/summary | ペルソナ統計 |
| `manifesto.py` | GET /manifesto/comparison | マニフェスト比較 |

#### 1.4.2 サービスレイヤー

コアサービス群とその依存関係:

```
SimulationEngine
├── PersonaGenerator / DemographicPersonaGenerator
├── VoteCalculator (6要因モデル)
├── LLMVoter (OpenRouter → Claude Sonnet 4)
├── ResultAggregator (選挙区集計 + ドント式比例配分)
└── Validators (7項目のバリデーション)

ExperimentManager
├── ID生成・ディレクトリ作成
├── Config スナップショット (SHA256)
└── メタデータ記録

ExperimentComparison
├── compare_results() (2結果セットの比較)
├── compare_experiments() (2実験IDの比較)
└── compare_with_actual() (実選挙結果との比較)

PredictionPipeline
├── Stage 1: Perplexity (ニュース分析)
├── Stage 2: Grok (SNS感情分析)
└── Stage 3: Claude (統合・最終判定)
```

#### 1.4.3 データベース・モデルレイヤー

**主要テーブル:**

| テーブル | 主キー | 主な列 | レコード数 |
|---------|-------|--------|-----------|
| `districts` | id (str) | prefecture, name, registered_voters | 289 |
| `candidates` | id (int) | district_id, name, party_id, is_incumbent | 1,120+ |
| `parties` | id (str) | name_ja, color, leader, coalition_group | 13 |
| `proportional_blocks` | id (str) | name, total_seats, prefectures | 11 |
| `predictions` | id | district_id, predicted_winner, confidence | 289 |
| `youtube_channels` | id | channel_id, party_id, subscriber_count | ~120 |
| `youtube_videos` | id | video_id, title, sentiment_score | ~1,200 |
| `youtube_sentiments` | id | party_id, positive/neutral/negative_ratio | ~10 |
| `news_articles` | id | title, source, sentiment_score | ~500 |

### 1.5 フロントエンドアーキテクチャ

#### 14ページ構成 (Next.js App Router)

| ページ | パス | 機能 |
|-------|------|------|
| Dashboard | `/` | メイン概要 (議席分布, 接戦区, 統計) |
| Simulation | `/simulation` | シミュレーション実行 (パイロット/全区) |
| Districts | `/districts` | 選挙区一覧・検索 |
| District Detail | `/district/[id]` | 候補者・予測履歴 |
| Predictions | `/predictions` | 最新予測一覧 |
| Battleground | `/battleground` | 接戦区フォーカス |
| Map | `/map` | 都道府県別インタラクティブ地図 |
| Proportional | `/proportional` | 比例ブロック結果 |
| YouTube | `/youtube` | YouTubeチャンネル分析 |
| News | `/news` | ニュース感情分析 |
| Personas | `/personas` | 投票者アーキタイプ |
| Manifesto | `/manifesto` | 政党政策比較 |
| Comparison | `/comparison` | 実験比較UI |
| Opinions | `/opinions` | 投票理由分析 |

#### 17チャートコンポーネント

`frontend/src/components/charts/` に配置:
- `SeatDistribution.tsx` - 政党別議席棒グラフ
- `DistrictVoteDistribution.tsx` - 得票分布
- `SeatComparisonChart.tsx` - 実験間議席比較
- `PersonaPartyHeatmap.tsx` - アーキタイプ x 政党ヒートマップ
- `ExperimentRankingTable.tsx` - 実験ランキング
- `DistrictComparisonTable.tsx` - 選挙区精度テーブル
- `AccuracyScorecard.tsx` - モデル精度スコアカード
- `AbstentionReasonsChart.tsx` - 棄権理由分析
- `SwingFactorsChart.tsx` - スイング要因分析
- `JapanMap.tsx` - 都道府県別地図
- 他7種 (PollingChart, YouTubeDailyChart, NewsDailyChart 等)

### 1.6 インフラ・デプロイメント

**Docker Compose (3サービス):**

| サービス | イメージ | ポート | 役割 |
|---------|---------|-------|------|
| `db` | postgres:16-alpine | 5432 | PostgreSQL |
| `backend` | Python 3.12 + FastAPI | 8000 | API サーバー |
| `frontend` | Node.js + Next.js | 3000 | UIサーバー |

### 1.7 データフローダイアグラム

```
┌─────────────────────────────────────────────────────┐
│  1. ペルソナ生成                                      │
│  persona_config.json + districts CSV                  │
│  → 100ペルソナ/選挙区 × 289選挙区 = 28,900ペルソナ     │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  2. 投票決定 (ハイブリッドTwo-Tier)                    │
│  Tier 1: ルールベース (6要因モデル) → 全ペルソナ        │
│  Tier 2: LLM (Claude) → needs_llm=true のみ          │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  3. 集計・ドント式比例配分                              │
│  SMD: 選挙区別候補者得票 → 当選者決定                   │
│  PR: 11ブロック別政党得票 → ドント式176議席配分          │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  4. バリデーション・実験記録                             │
│  validators.py → 7項目チェック                         │
│  ExperimentManager → metadata.json, CSV, summary     │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  5. 可視化 (Frontend)                                 │
│  議席分布 / 選挙区詳細 / 実験比較 / 地図                │
└─────────────────────────────────────────────────────┘
```

---

## 2. 実験の並列処理

### 2.1 選挙区レベルの並列化

`SimulationEngine._run_districts_parallel()` (`engine.py:191-222`) で `ThreadPoolExecutor` を使用。

```
SimulationEngine.run_all()
        │
        ▼
_run_districts_parallel(289 districts)
        │
        ├── ThreadPoolExecutor(max_workers=8)
        │
        ├── Thread 1: run_district(東京1区)
        ├── Thread 2: run_district(大阪1区)
        ├── Thread 3: run_district(北海道1区)
        │   ...
        └── Thread 8: run_district(沖縄1区)
            │
            各スレッド内:
            1. ペルソナ生成 (100名)
            2. ルールベース投票計算 (全100名)
            3. LLMバッチ処理 (needs_llm=trueのみ)
            4. 結果集計
```

**パラメータ:**

| パラメータ | デフォルト値 | 設定元 | 説明 |
|-----------|------------|-------|------|
| `max_workers` | 8 | `MAX_DISTRICT_WORKERS` env or コンストラクタ | 同時実行スレッド数 |
| デバッグモード | 1 | `max_workers=1` で逐次実行 | デバッグ用 |

### 2.2 LLMバッチの非同期処理

`llm_voter.py` で AsyncIO + Semaphore を使用したLLM呼び出しの並行制御。

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| バッチサイズ | 15ペルソナ/呼び出し | 1回のLLM APIコールに含めるペルソナ数 |
| 並行数 | 3-5 (Semaphore) | 同時LLM APIリクエスト数 |
| モデル | `claude-sonnet-4-20250514` | OpenRouter経由 |
| temperature | 0.7 | 生成の多様性 |
| max_tokens | 2000 | 応答の最大トークン数 |

### 2.3 スレッドセーフ設計

各選挙区は独立したローカルRNG（乱数生成器）を使用:

```python
# engine.py:99
rng = random.Random(self.seed + hash(district_id) % 10000)
```

- **目的**: 並列実行時にグローバル乱数状態が共有されることを防止
- **再現性**: 同一シード + 同一選挙区IDで常に同一の乱数列を生成
- **独立性**: 選挙区の実行順序が変わっても結果は同一

### 2.4 パフォーマンス特性

| 実行モード | 選挙区数 | LLM呼び出し | 実行時間 (実測) | 推定コスト |
|-----------|---------|------------|---------------|-----------|
| パイロット (ルールベース) | 10 | 0 | < 10秒 | $0 |
| パイロット (LLM) | 10 | ~67バッチ | 約11-19分 | $5-10 |
| パイロット (議論) | 10 | ~300バッチ | 約102分 | $15-25 |
| パイロット (時系列) | 10 | ~350バッチ | 約180分 | $20-30 |
| 全区 (ルールベース) | 289 | 0 | < 1分 | $0 |
| 全区 (LLM) | 289 | ~1,930バッチ | ~数時間 | $30-60 |
| 全区 (ハイブリッド) | 289 | ~507バッチ (76区分) | ~30分 | $15-20 |

---

## 3. 実験管理

### 3.1 ExperimentManager クラスの設計

`backend/app/services/experiment_manager.py` に定義。実験のライフサイクル全体を管理。

| メソッド | 機能 |
|---------|------|
| `generate_experiment_id(seed)` | タイムスタンプ + シードでID生成 |
| `create_experiment_dir(experiment_id)` | `results/experiments/{id}/` を作成 |
| `snapshot_configs()` | persona_config.json, manifesto_policies.json のSHA256スナップショット |
| `write_metadata()` | パラメータ、実行時間、gitコミット、結果サマリを記録 |
| `write_validation_report()` | バリデーション結果をJSON出力 |
| `list_experiments()` | 全実験一覧をメタデータ付きで返却 |
| `load_experiment(id)` | メタデータ + district_results.csv + summary.json を読み込み |
| `load_opinions(id)` | persona_decisions.json から投票理由・スイング要因を集約 |

### 3.2 実験ID体系

| コンテキスト | フォーマット | 例 |
|-------------|------------|-----|
| スクリプト経由 | `v{N}a_YYYYMMDD_HHMMSS_seed{N}` | `v8a_20260208_141946_seed42` |
| API経由 | `sim_YYYYMMDD_HHMMSS_seed{N}` | `sim_20260208_150000_seed42` |

### 3.3 実験ディレクトリ構造

```
results/experiments/{experiment_id}/
├── metadata.json              # パラメータ、実行時間、gitコミット
├── district_results.csv       # SMD結果 (district_id, winner, margin, turnout)
├── proportional_results.csv   # 比例結果 (block, party, seats_won)
├── summary.json               # 全国集計 (議席数, 投票率, 過半数判定)
├── persona_decisions.json     # ペルソナ別投票データ (500KB+)
├── validation_report.json     # バリデーション結果
└── config_snapshot/           # 設定の凍結コピー
    ├── persona_config.json
    └── manifesto_policies.json
```

### 3.4 メタデータスキーマ

```json
{
  "experiment_id": "v8a_20260208_141946_seed42",
  "created_at": "2026-02-08T14:19:46+09:00",
  "status": "completed",
  "duration_seconds": 661.95,
  "description": "キャリブレーション付きLLM投票 (デカップリング方式)",
  "tags": ["calibrated", "pilot"],
  "parameters": {
    "seed": 42,
    "personas_per_district": 100,
    "llm_batch_size": 15,
    "model": "claude-sonnet-4-20250514",
    "mode": "pilot",
    "district_count": 10,
    "factor_weights": null,
    "swing_noise_offset": 0.0,
    "generator_type": "archetype",
    "turnout_boost": 0.0
  },
  "results_summary": {
    "national_turnout_rate": 0.491,
    "smd_seats": {"ldp": 5, "chudo": 3, "ishin": 1, "other": 1},
    "validation_passed": true
  },
  "config_versions": {
    "persona_config_hash": "sha256:a1b2c3...",
    "manifesto_policies_hash": "sha256:d4e5f6..."
  }
}
```

### 3.5 バリデーションチェック項目

`validators.py` で実施される検証:

| チェック項目 | 内容 | 閾値 |
|-------------|------|------|
| ペルソナ数 | 各選挙区のペルソナ数が設定値と一致 | 100 |
| 投票率範囲 | 選挙区別投票率が合理的範囲内 | 5-60% |
| 得票整合性 | 投票者数 = 各候補者得票の合計 | 完全一致 |
| 当選者妥当性 | 当選者得票 >= 次点得票 | 必須 |
| 負の値なし | 全得票が0以上 | >= 0 |
| 選挙区ID有効性 | 全district_idが有効なフォーマット | XX_N |
| 比例票整合性 | 比例投票者数 <= 投票者数 | 必須 |

---

## 4. モデル管理

### 4.1 6要因投票決定モデル (ルールベース)

`vote_calculator.py` に実装。各候補者のスコアを6つの要因の加重和で計算。

| 要因 | 重み | 説明 | スコア計算 |
|------|-----|------|-----------|
| `party_loyalty` | 0.30 | 政党忠誠度 | 支持政党一致=1.0, 無党派=0.3, 他党=0.1 |
| `policy_alignment` | 0.25 | 政策一致度 | manifesto_policies.jsonの政党-アーキタイプスコア |
| `candidate_appeal` | 0.20 | 候補者魅力 | 現職+0.3, 元職+0.15, 当選回数x0.05 (上限0.2) |
| `media_influence` | 0.10 | メディア影響 | 政党支持率を代理変数として使用 |
| `local_connection` | 0.10 | 地域つながり | 現職+0.3 (地元活動の蓄積) |
| `strategic_voting` | 0.05 | 戦略的投票 | 現職+0.2, 比例重複-0.1 |

**スコア計算式:**
```
candidate_score = Σ(weight_i × factor_score_i) + Gaussian(0, noise_level)
```

### 4.2 スイング閾値とLLM委譲

ペルソナの `swing_tendency` によりノイズレベルとLLM委譲を決定:

| スイングレベル | ノイズ (σ) | LLM委譲 | 想定有権者像 |
|-------------|-----------|---------|-------------|
| `very_low` | 0.05 | No | 固定支持層 (組織票) |
| `low` | 0.10 | No | 緩やかな支持層 |
| `moderate` | 0.20 | **Yes** | 判断に迷う層 |
| `moderate_high` | 0.25 | **Yes** | スイング有権者 |
| `high` | 0.35 | **Yes** | 浮動票層 |
| `very_high` | 0.45 | **Yes** | 完全な浮動票 |

### 4.3 ハイブリッド Two-Tier アーキテクチャ

```
全ペルソナ (100名/選挙区)
        │
        ▼
┌───────────────────────────────┐
│  Step 1: 投票/棄権判定         │
│  turnout_probability vs random │
│  → 棄権理由生成                │
└───────────┬───────────────────┘
            │ (投票者のみ)
            ▼
┌───────────────────────────────┐
│  Step 2: 6要因スコア計算       │
│  全候補者にスコア付与           │
│  swing_tendency を評価          │
└───────┬───────────┬───────────┘
        │           │
   Low swing    Mid-High swing
        │           │
        ▼           ▼
┌──────────┐  ┌──────────────┐
│ Tier 1   │  │ Tier 2       │
│ ルール   │  │ LLM (Claude) │
│ 確定投票 │  │ バッチ処理    │
└────┬─────┘  └──────┬───────┘
     │               │
     └───────┬───────┘
             ▼
┌───────────────────────────────┐
│  Step 3: 集計 + ドント式配分   │
│  SMD当選者 + PR議席配分        │
└───────────────────────────────┘
```

### 4.4 v8a デカップリングモデル (3段階パイプライン)

Phase 2のLLM実験で発見されたバイアス（投票率過大予測75-88%、中道政党偏重）を解消するために設計。

| Stage | 処理 | 担当 | 目的 |
|-------|------|------|------|
| **Stage 1** | 投票/棄権判定 | ルールベース (`determine_turnout()`) | 投票率過大予測の防止 |
| **Stage 2** | 候補者選択 | LLM (分布アンカー付きプロンプト) | 人間らしい判断の確保 |
| **Stage 3** | 事後キャリブレーション | ルールベース (`calibrate_decisions()`) | 分布偏りの補正 |

**Stage 3 キャリブレーションのアルゴリズム:**

1. 現在のLLM出力における政党分布を集計
2. 選挙区の過去支持率分布（ターゲット分布）と比較
3. 過大代表政党 (current > target + 1%) と過小代表政党 (current < target - 1%) を特定
4. 過大代表政党の一部の票を過小代表政党に確率的にフリップ:
   - フリップ確率 = (超過分) x strength (0.3)
   - フリップ先は過小代表の度合いで重み付け
5. フリップされた票の確信度を 0.8倍に低下

**キャリブレーション強度パラメータ:**
- `strength=0.0`: 補正なし (v8b相当)
- `strength=0.3`: 標準 (ギャップの30%を補正)
- `strength=1.0`: 完全整合 (過去分布に完全一致)

### 4.5 v10b メモリモデル

SQLite 3層ストア (`memory/store.py`) による学習的要素の導入。

```
┌─────────────────────────────────────────────┐
│  Layer 1: Episodes (エピソード記憶)           │
│  experiment_id, district_id, turnout_rate,   │
│  winner_party, party_vote_shares             │
│  → 過去のシミュレーション結果を蓄積            │
├─────────────────────────────────────────────┤
│  Layer 2: Calibration Signals (補正信号)      │
│  district_id, party_id, target_share,        │
│  predicted_share, correction_needed           │
│  → LLMバイアスのパターンを記録                 │
├─────────────────────────────────────────────┤
│  Layer 3: Trends (トレンド分析)               │
│  district_id, party_id, run_count,            │
│  avg_vote_share, stddev, trend_direction      │
│  → 複数実験の統計的傾向を集約                   │
└─────────────────────────────────────────────┘
```

**外部データ統合:**
- `past_elections.json`: 2021衆院選、2022参院選、2024衆院選、2025参院選の結果
- `economic_context.json`: GDP成長率、CPI、失業率、実質賃金、日経平均

### 4.6 プロンプトエンジニアリング体系

プロンプトは `prompts.py` で管理され、実験バージョンに応じて進化:

| プロンプト | 使用バージョン | 特徴 |
|-----------|-------------|------|
| `SYSTEM_PROMPT` | v4a-v7a | 投票行動シミュレーター、投票率判定をLLMに委ねる |
| `CALIBRATED_SYSTEM_PROMPT` | v8a-v9a | 投票率判定を除外、分布アンカリング指示を追加 |
| `MEMORY_SYSTEM_PROMPT` | v10b | 過去選挙・経済コンテキストの注入 |

**バッチプロンプト (`build_batch_prompt()`) の構成要素:**

1. **候補者情報**: 名前、政党、現職/新人、当選回数、比例重複
2. **選挙区コンテキスト**: 過去支持率（8政党分）、浮動票率、地域課題
3. **全国情勢**: 首相名、連立構造、主要争点、天候情報
4. **ペルソナ属性**: アーキタイプ、年齢、性別、職業、関心事、情報源、政党支持、イデオロギー
5. **タスク指示**: JSON配列で投票判断を返すよう指定

---

## 5. 既存データの整理

### 5.1 データファイル一覧

| データファイル | パス | 形式 | レコード数 | 用途 |
|-------------|------|------|-----------|------|
| 選挙区定義 | `backend/app/data/districts_sample.json` | JSON | 289区 | 選挙区マスタ (候補者情報含む) |
| 候補者データ | `backend/app/data/candidates.csv` | CSV | 1,120+ | 実在候補者 (名前, 政党, 現職/新人) |
| 政党マスタ | `backend/app/data/parties.json` | JSON | 13 | 政党名, カラー, 連立区分 |
| 比例ブロック | `backend/app/data/proportional_blocks.json` | JSON | 11 | ブロック名, 議席数, 対象都道府県 |
| 都道府県 | `backend/app/data/prefectures.json` | JSON | 47 | 都道府県コード, 比例ブロック所属 |
| ペルソナ分布 | `persona_data/districts/all_districts_persona_data.csv` | CSV | 289 x ~50列 | 選挙区別アーキタイプ構成比率 |
| ペルソナ設定 | `persona_data/persona_config.json` | JSON | 15アーキタイプ | 属性分布, 投票率, スイング傾向 |
| マニフェスト | `persona_data/manifesto_policies.json` | JSON | 8政党 x 政策領域 | 政策-アーキタイプ整合スコア |
| 政治傾向 | `persona_data/political_tendencies.json` | JSON | 47都道府県 | 地域別政治傾向 |
| 社会経済指標 | `persona_data/socioeconomic_indicators.json` | JSON | 47都道府県 | 人口, 所得, 産業構造 |
| 過去選挙 | `persona_data/past_elections.json` | JSON | 4選挙分 | 2021/2022/2024/2025結果 |
| 経済コンテキスト | `persona_data/economic_context.json` | JSON | ~10指標 | GDP/CPI/失業率/実質賃金 |
| 地域課題 | `persona_data/regional_issues.json` | JSON | 84KB | 都道府県別優先課題 |
| YouTubeチャンネル | `persona_data/youtube/{date}/channels.csv` | CSV | ~120 | 政党別YouTube活動 |
| YouTube動画 | `persona_data/youtube/{date}/videos.csv` | CSV | ~1,200 | 動画メトリクス + 感情分析 |
| メモリDB | `memory/agent_memory.db` | SQLite | 動的 | 3層メモリストア (v10b) |

### 5.2 ペルソナデータ構造の比較

| 属性 | アーキタイプ型 (v1-v9) | 人口統計型 (v10) |
|------|---------------------|-----------------|
| 生成方法 | 15固定アーキタイプから抽選 | 国勢調査データから統計的サンプリング |
| 年齢 | アーキタイプ範囲内 (例: 20-35) | 6帯域の分布から直接サンプリング |
| 性別 | 固定比率 (48%男/52%女) | 選挙区別実態分布 |
| 職業 | アーキタイプ別職種プール | 産業セクター別 (1次/2次/3次) |
| 収入 | アーキタイプから暗黙的推定 | 明示的3段階 (低/中/高) |
| 教育 | モデル化なし | 3段階 (高卒以下/専門卒/大卒以上) |
| 世帯類型 | モデル化なし | 5類型 (単身/夫婦/核家族/3世代/その他) |
| 都市化度 | アーキタイプから暗黙的推定 | 4段階 (大都市/中核市/地方都市/農村部) |
| データ依存 | persona_config.json | all_districts_persona_data.csv + 経済データ |

### 5.3 15アーキタイプ一覧

| ID | 日本語名 | 年齢帯 | 想定投票率 | スイング傾向 |
|----|---------|-------|-----------|------------|
| urban_young_worker | 都市部若年勤労者 | 20-35 | 低 | high |
| suburban_family | 郊外子育て世帯 | 30-45 | 中 | moderate |
| middle_aged_salaryman | 中高年会社員 | 40-55 | 中-高 | moderate |
| middle_aged_working_woman | 中高年女性勤労者 | 40-55 | 中 | moderate_high |
| rural_farmer | 農村部農業従事者 | 50-70 | 高 | very_low |
| active_elderly | アクティブ高齢者 | 65-74 | 高 | low |
| late_elderly | 後期高齢者 | 75+ | 中-高 | very_low |
| self_employed | 自営業者 | 35-60 | 中 | moderate |
| public_sector_worker | 公務員 | 30-55 | 高 | low |
| university_student | 大学生 | 18-22 | 低 | very_high |
| homemaker | 専業主婦/主夫 | 30-55 | 低-中 | moderate_high |
| non_regular_worker | 非正規雇用者 | 25-50 | 低 | high |
| labor_union_member | 労働組合員 | 35-55 | 高 | very_low |
| tech_worker | IT技術者 | 25-45 | 低-中 | high |
| freelance_gig_worker | フリーランス/ギグ | 25-40 | 低 | very_high |

---

## 6. 実験条件の整理

### 6.1 Phase 1: ルールベース実験 (v1-v3c)

全ペルソナの投票行動を **6要因加重モデル + ガウシアンノイズ** で決定。LLM呼び出しなし。

| 実験 | 方式 | 選挙区 | シード | 主な変更点 |
|------|------|--------|--------|-----------|
| v1 | ルールベース | 10 (パイロット) | 42 | ベースライン |
| v2 | ルールベース | 289 (全区) | 42,123,7,99,314 | v1の全区展開 |
| v3a | ルールベース | 289 | 42,99,123 | policy_alignment ↑0.35, party_loyalty ↓0.20 |
| v3b | ルールベース | 289 | 42,99,123 | party_loyalty ↓0.15, swing_noise +0.05 |
| v3c | ルールベース | 289 | 42,99,123 | turnout_boost +0.08 |

**限界**: ペルソナの職業・関心事・情報源は生成されるが、投票決定には直接使われない。「電卓」であり「ペルソナAI」ではない。

### 6.2 Phase 2: LLMペルソナ実験 (v4a-v7a)

ペルソナの投票行動をLLM（Claude Sonnet 4）に委ねる。

| 実験 | 方式 | 選挙区 | コンセプト | 実行時間 | 推定コスト |
|------|------|--------|-----------|---------|-----------|
| v4a | LLM全ペルソナ | 10 | ペルソナになりきって投票判断 | 19分 | ~$5-10 |
| v5a | ペルソナ間議論 | 10 | 5人グループで議論後に投票 | 102分 | ~$15-25 |
| v6a | 時系列イベント反応 | 10 | 5日間のニュースに反応しつつ投票 | 180分 | ~$20-30 |
| v7a | 理由付き投票 | 10 | 投票理由を自然言語で説明 | 40分 | ~$40-60 |

**設計原則:**
- ペルソナ固定: 同一シード・同一分布でペルソナを生成
- 候補者固定: 実在候補者データをそのまま使用
- 比較可能性: v2をベースラインとして差分比較

### 6.3 Phase 3: キャリブレーション実験 (v8a-v9a)

Phase 2で発見されたLLMバイアスを補正。

| 実験 | 方式 | 選挙区 | コンセプト | 推定コスト |
|------|------|--------|-----------|-----------|
| v8a | デカップリングLLM | 10→289 | 投票率ルールベース+投票先LLM+事後キャリブレーション | ~$5-45 |
| v8b | 分布アンカリングLLM | 10 | v8aからキャリブレーションを除外（比較用） | ~$5 |
| v9a | ハイブリッドアンサンブル | 289 | 安定区ルールベース+接戦区LLM | ~$15-20 |

### 6.4 Phase 4: 人口統計・記憶実験 (v10a-v10b)

| 実験 | 方式 | コンセプト |
|------|------|-----------|
| v10a | 人口統計ペルソナ | 15アーキタイプ→国勢調査ベースの人口統計的ペルソナに移行 |
| v10b | メモリシステム | 過去選挙結果・経済データをメモリとして保持し、LLM判断に活用 |

### 6.5 全実験条件サマリー

| パラメータ | v1-v3 | v4a-v7a | v8a | v9a | v10a | v10b |
|-----------|-------|---------|-----|-----|------|------|
| ペルソナ生成 | アーキタイプ | アーキタイプ | アーキタイプ | アーキタイプ | **人口統計** | **人口統計** |
| 投票率判定 | ルール | **LLM** | **ルール** | ハイブリッド | ルール | ルール |
| 候補者選択 | ルール | **LLM** | **LLM** | ハイブリッド | LLM | **メモリ付きLLM** |
| キャリブレーション | なし | なし | **あり (0.3)** | 接戦区のみ | あり | あり |
| メモリ | なし | なし | なし | なし | なし | **あり (3層)** |
| シード | 42 | 42 | 42 | 42 | 42 | 42 |
| ペルソナ数/区 | 100 | 100 | 100 | 100 | 100 | 100 |
| モデル | N/A | Claude Sonnet 4 | Claude Sonnet 4 | Claude Sonnet 4 | Claude Sonnet 4 | Claude Sonnet 4 |
| temperature | N/A | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 |

### 6.6 共通パラメータ vs 可変パラメータ

**共通 (全実験):**
- `seed=42` (標準)
- `personas_per_district=100`
- `llm_batch_size=15`
- 候補者データ: 同一 (`candidates.csv`)
- 選挙区データ: 同一 (`districts_sample.json`)

**可変:**
- `generator_type`: "archetype" (v1-v9) / "demographic" (v10)
- `factor_weights`: v3a/v3bで調整
- `swing_noise_offset`: v3bで+0.05
- `turnout_boost`: v3cで+0.08
- `model`: v4以降で`claude-sonnet-4-20250514`
- キャリブレーション強度: v8aで0.3
- メモリ: v10bで有効化

---

## 7. 実験結果の比較ポイント

### 7.1 定量比較指標の定義

`experiment_comparison.py` で定義される比較指標:

| 指標 | 定義 | 値の範囲 | 理想値 |
|------|------|---------|-------|
| `winner_match_rate` | 当選者政党の一致率 | 0.0-1.0 | 1.0 |
| `seat_mae` | 政党別議席数の平均絶対誤差 | 0- | 0 |
| `turnout_correlation` | 選挙区別投票率のPearson相関 | -1.0-1.0 | 1.0 |
| `battleground_accuracy` | 票差下位25%選挙区での当選者一致率 | 0.0-1.0 | 1.0 |
| `government_prediction` | 与党過半数(233議席)予測の正否 | True/False | True |
| `margin_correlation` | 得票差のPearson相関 | -1.0-1.0 | 1.0 |
| `turnout_diff` | 全国投票率の差（絶対値） | 0- | 0 |

### 7.2 全実験結果比較テーブル

| 指標 | v1 (ルール) | v4a (LLM) | v5a (議論) | v6a (時系列) | v7a (理由付き) | v8a (キャリブ) |
|------|-----------|-----------|-----------|-------------|-------------|-------------|
| **投票率** | 54.6% | 75.5% | 49.5% | 72.3% | 88.7% | **49.1%** |
| **LDP議席** (10区) | ~6 | 4 | 5 | 3 | 6 | 5 |
| **Chudo議席** (10区) | ~1 | 5 | 4 | 6 | 3 | 3 |
| **Ishin議席** (10区) | ~2 | 1 | 1 | 1 | 1 | 1 |
| **v1一致率** | 100% | 60% | 70% | 50% | 80% | - |
| **実行時間** | <10秒 | 19分 | 102分 | 180分 | 40分 | 11分 |
| **推定コスト** | $0 | ~$5-10 | ~$15-25 | ~$20-30 | ~$40-60 | ~$5 |

### 7.3 LLMバイアスの検出と定量化

Phase 2の実験から以下のバイアスが系統的に検出された:

**1. 投票率過大予測バイアス**

| 実験 | 投票率 | 現実的範囲(50-55%)との乖離 |
|------|-------|--------------------------|
| v4a (LLM個人) | 75.5% | +20.5% |
| v5a (議論) | 49.5% | 範囲内 (設計上50人/100人制限) |
| v6a (時系列) | 72.3% | +17.3% |
| v7a (理由付き) | 88.7% | +33.7% (最大) |
| **v8a (キャリブ)** | **49.1%** | **範囲内** |

**2. 中道政党 (Chudo) バイアス**

| 実験 | Chudo議席 (10区中) | v1からの変動 |
|------|-------------------|------------|
| v1 (ルール) | ~1 | - |
| v4a (LLM個人) | 5 | +4 |
| v5a (議論) | 4 | +3 |
| v6a (時系列) | **6** | **+5** (最大) |
| v7a (理由付き) | 3 | +2 |
| **v8a (キャリブ)** | **3** | **+2** (軽減) |

**3. 都市 vs 農村の感度差**

- 農村・保守地盤（秋田、島根）: LLM/ルールベースとも安定してLDP
- 都市部・接戦区（東京、神奈川、愛知、京都）: LLMは野党寄りの判断傾向

### 7.4 v8aキャリブレーションの補正効果

| 指標 | v4a (補正前) | v8a (補正後) | 改善 |
|------|------------|------------|------|
| 投票率 | 75.5% | 49.1% | 現実的範囲に正規化 |
| Chudo議席 | 5/10 | 3/10 | 中道バイアス40%軽減 |
| 実行時間 | 19分 | 11分 | 42%短縮 (投票者のみLLM) |
| 推定コスト | $5-10 | ~$5 | 投票者限定でコスト削減 |

---

## 8. 改善ポイントの列挙

### 8.1 モデル精度

| 改善項目 | 現状 | 改善案 | 優先度 |
|---------|------|-------|-------|
| score_breakdownの未活用 | VoteDecisionにscore_breakdownが記録されるが、LLMフォールバック時に参照されない | LLMプロンプトにルールベーススコアの分布を注入し、アンカーとして活用 | 高 |
| 単一モデル依存 | Claude Sonnet 4のみ使用 | GPT-4o、Geminiとのアンサンブル比較 | 中 |
| 投票率モデルの精緻化 | 単純な確率閾値 | 年齢・天候・地域の交互作用モデル | 中 |

### 8.2 ペルソナ生成

| 改善項目 | 現状 | 改善案 | 優先度 |
|---------|------|-------|-------|
| 属性の網羅性 | 基本的人口統計 + 関心事 | 宗教観、メディア消費量、SNS利用パターンの追加 | 中 |
| 分布の検証 | 選挙区別構成比のみ | 国勢調査マイクロデータとの適合度検定 | 高 |
| ペルソナ間相関 | 独立生成 | 世帯単位の相関（夫婦の政党支持相関等） | 低 |

### 8.3 並列処理・スケーラビリティ

| 改善項目 | 現状 | 改善案 | 優先度 |
|---------|------|-------|-------|
| ThreadPool→ProcessPool | ThreadPoolExecutor (GIL制約あり) | ProcessPoolExecutor or Ray for CPU-bound処理 | 低 (LLM呼び出しがボトルネックのため) |
| LLMバッチAPI | リアルタイムAPI呼び出し | OpenRouter Batch API活用でコスト50%削減 | 高 |
| キャッシュ | 同一ペルソナの再計算 | ルールベース結果のRedisキャッシュ | 低 |

### 8.4 プロンプトエンジニアリング

| 改善項目 | 現状 | 改善案 | 優先度 |
|---------|------|-------|-------|
| temperatureの最適化 | 固定0.7 | 0.3-1.0の系統的探索（投票率・一致率のトレードオフ分析） | 高 |
| プロンプトA/Bテスト | 手動切り替え | プロンプトバリアントのランダム化比較フレームワーク | 中 |
| Few-shot | なし | 過去選挙の出口調査データからの投票判断例の提供 | 中 |
| Chain-of-Thought | v7aで限定的 | 全実験での段階的推論の標準化 | 中 |

### 8.5 バリデーション・テスト

| 改善項目 | 現状 | 改善案 | 優先度 |
|---------|------|-------|-------|
| ユニットテスト | 不足 | シミュレーションモジュールのpytest整備 | 高 |
| クロスバリデーション | 未実装 | k-fold（シード分割）による統計的信頼区間の算出 | 高 |
| 感度分析 | 手動 | factor_weightsの自動グリッドサーチ | 中 |
| 回帰テスト | なし | CIパイプラインでの結果再現性チェック | 中 |

### 8.6 フロントエンド・可視化

| 改善項目 | 現状 | 改善案 | 優先度 |
|---------|------|-------|-------|
| リアルタイム進捗 | なし | WebSocket/SSEによるシミュレーション進捗表示 | 中 |
| 比較画面 | 2実験比較 | N実験のマトリクス比較、散布図、ヒートマップ | 中 |
| インタラクティブ分析 | 静的チャート | ドリルダウン可能な選挙区別詳細 | 低 |

### 8.7 再現性と実験管理

| 改善項目 | 現状 | 改善案 | 優先度 |
|---------|------|-------|-------|
| コスト追跡 | 推定のみ | OpenRouter APIの実使用量ログの自動記録 | 高 |
| 自動キャリブレーション | 手動strength設定 | メモリシステムからの自動フィードバックループ | 中 |
| 実験比較ダッシュボード | 基本テーブル | MLflow/Weights & Biases統合 | 低 |
| git連携 | コミットハッシュ記録のみ | 実験ブランチの自動作成・タグ付け | 低 |

---

## 9. 先行研究の列挙と技術ポイントの比較

### 9.1 先行研究一覧

| # | 論文/研究 | 年 | 主なテーマ | 本プロジェクトとの関連 |
|---|---------|---|---------|---------------------|
| 1 | **Argyle et al. "Out of One, Many"** | 2023 | LLMによる合成世論調査、事後キャリブレーション（raking） | v8a Stage 3キャリブレーションの直接的インスピレーション |
| 2 | **Park et al. "Generative Agents"** | 2023 | 25エージェントのメモリ付き生活シミュレーション (Stanford) | v10bメモリシステム（エピソード記憶+リフレクション）の参考 |
| 3 | **Horton "LLMs as Simulated Economic Agents"** | 2023 | LLMが経済実験で人間類似の行動を示す | ペルソナベース投票シミュレーションの理論的妥当性を支持 |
| 4 | **Kim & Lee "Can ChatGPT Predict Elections?"** | 2023 | ChatGPTによる選挙結果の直接予測 | 本プロジェクトのペルソナ分解アプローチとの対比 |
| 5 | **Aher et al. "Using LLMs to Simulate Multiple Humans"** | 2023 | マルチペルソナシミュレーション、チューリングテスト | 100ペルソナ/選挙区のマルチエージェント手法の先行 |
| 6 | **Bisbee et al. "Synthetic Replacements for Human Survey Data"** | 2024 | LLM生成の合成調査データ、人口統計的重み付け | v10aの人口統計ベースペルソナ生成に対応 |
| 7 | **Brand et al. "Using GPT for Market Research"** | 2023 | LLMによる大規模消費者調査シミュレーション | 政策-ペルソナ整合スコアリングの参考 |
| 8 | **Fishkin et al. "Deliberative Polling"** | 2018 | 熟議型世論調査の方法論 | v5aの議論シミュレーション設計の理論的背景 |

### 9.2 技術ポイント比較テーブル

| 技術ポイント | Argyle (2023) | Park (2023) | Kim & Lee (2023) | Aher (2023) | **本プロジェクト** |
|------------|-------------|-------------|-----------------|-------------|-----------------|
| **手法** | 合成世論調査 | エージェントシミュレーション | 直接予測 | マルチペルソナ | **ハイブリッドRule+LLM** |
| **規模** | 数千サンプル | 25エージェント | 単一予測 | 実験室規模 | **289選挙区 x 100 = 28,900ペルソナ** |
| **ペルソナ** | 人口統計プロファイル | 詳細なバックストーリー | なし | 実験参加者模倣 | **15アーキタイプ or 国勢調査ベース** |
| **メモリ** | なし | エピソード+リフレクション | なし | なし | **3層SQLite (v10b)** |
| **キャリブレーション** | 事後raking | なし | なし | なし | **3段階 (デカップリング+分布アンカー+事後補正)** |
| **投票率モデル** | 含まれない | 含まれない | 含まれない | 含まれない | **ルールベース分離 (v8a)** |
| **コスト最適化** | 考慮なし | 考慮なし | 1回の呼び出し | 考慮なし | **ハイブリッド: 安定区ルール+接戦区LLM** |
| **実選挙比較** | 世論調査との比較 | 行動の自然さ | 選挙結果 | チューリングテスト | **選挙結果 + 6指標の定量比較** |
| **議論/相互作用** | なし | 自然言語対話 | なし | なし | **v5aグループ議論** |
| **時系列** | 静的 | 動的(日次) | 静的 | 静的 | **v6a 5日間イベント反応** |

### 9.3 本プロジェクトの新規性

1. **ハイブリッドTwo-Tier**: ルールベースとLLMの長所を組み合わせ、低スイング層には決定論的モデル、高スイング層にはLLMを適用。先行研究にはこのような段階的アプローチは見られない

2. **3段階キャリブレーション (v8a)**: Argyle et al.の事後キャリブレーションを拡張し、(1)投票率デカップリング、(2)分布アンカリングプロンプト、(3)事後分布補正の3段階で体系的にバイアスを補正

3. **大規模かつ実選挙対応**: 28,900ペルソナを289選挙区に配置し、実在候補者1,120名に対して投票シミュレーションを実行。先行研究の多くは実験室規模または架空シナリオ

4. **メソッド間の体系的比較**: v1-v10bの10種類以上の手法を同一条件で比較し、LLMバイアスの定量的特性（投票率過大予測、中道バイアス、理由付けの合理化効果）を明らかにした

5. **コスト最適化**: v9aのハイブリッドアンサンブルにより、安定区はルールベース（無料）、接戦区のみLLM（~76区分の$15-20）で全289区をカバー。先行研究ではコスト最適化の議論は少ない

6. **メモリ付き学習的シミュレーション (v10b)**: Park et al.のGenerative Agentsのメモリ概念を選挙シミュレーションに応用し、過去選挙結果と経済データの3層記憶で投票判断をコンテキスト化

---

## 付録

### A. 主要ファイルパス対応表

| コンポーネント | パス |
|-------------|------|
| FastAPI エントリポイント | `backend/app/main.py` |
| 設定管理 | `backend/app/config.py` |
| DB セッション | `backend/app/db/session.py` |
| シミュレーションエンジン | `backend/app/services/simulation/engine.py` |
| ペルソナ生成 (アーキタイプ) | `backend/app/services/simulation/persona_generator.py` |
| ペルソナ生成 (人口統計) | `backend/app/services/simulation/demographic_persona_generator.py` |
| 6要因投票モデル | `backend/app/services/simulation/vote_calculator.py` |
| LLM投票 | `backend/app/services/simulation/llm_voter.py` |
| プロンプト管理 | `backend/app/services/simulation/prompts.py` |
| 結果集計 | `backend/app/services/simulation/result_aggregator.py` |
| バリデーション | `backend/app/services/simulation/validators.py` |
| メモリストア | `backend/app/services/simulation/memory/store.py` |
| メモリ付きLLM投票 | `backend/app/services/simulation/memory/memory_llm_voter.py` |
| 実験管理 | `backend/app/services/experiment_manager.py` |
| 実験比較 | `backend/app/services/experiment_comparison.py` |
| 予測パイプライン | `backend/app/services/prediction_pipeline.py` |
| APIルーター | `backend/app/api/router.py` |
| シミュレーションAPI | `backend/app/api/simulation.py` |
| フロントエンドAPI通信 | `frontend/src/lib/api-client.ts` |
| TypeScript型定義 | `frontend/src/types/index.ts` |
| 実験ログ | `experiments/experiment_log.md` |
| Docker Compose | `docker-compose.yml` |

### B. 用語集

| 用語 (日) | 用語 (英) | 説明 |
|----------|----------|------|
| 小選挙区 | SMD (Single-Member District) | 289選挙区、各1名当選 |
| 比例代表 | PR (Proportional Representation) | 11ブロック、176議席をドント式配分 |
| ペルソナ | Persona | シミュレーション上の有権者エージェント |
| アーキタイプ | Archetype | 15種の有権者類型 |
| スイング傾向 | Swing Tendency | 投票先の不確実性レベル (very_low - very_high) |
| ドント式 | D'Hondt Method | 比例代表の議席配分アルゴリズム |
| キャリブレーション | Calibration | LLM出力の分布を過去データに近づける補正 |
| デカップリング | Decoupling | 投票率判定と候補者選択を分離する手法 |
| 分布アンカリング | Distribution Anchoring | プロンプトに過去支持率分布を含めて出力を制約 |
| ハイブリッドアンサンブル | Hybrid Ensemble | 安定区ルールベース+接戦区LLMの複合手法 |
| 浮動票 | Swing Votes | 特定政党に固定されない有権者の票 |
| 接戦区 | Battleground District | 得票差が小さく結果が不確定な選挙区 |
| 過半数 | Majority | 衆議院465議席の233議席 |
| 中道改革連合 | Chudo | 野党連合の略称 (コード上の識別子) |

---

*このドキュメントは2026年2月8日時点のコードベースに基づいて作成されています。*
