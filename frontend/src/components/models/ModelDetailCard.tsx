"use client";

import { useState } from "react";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import type { ModelComparisonEntry } from "@/types";

/**
 * 各予測モデルの詳細な計算式・重み・手法を定義
 * 参考: https://github.com/Taiyou/youtube-election-analysis-2026
 */
const MODEL_DETAILS: Record<
  number,
  {
    methodology: string;
    formula: string;
    weights: { label: string; value: number; description: string }[];
    parameters: { label: string; value: string }[];
    strengths: string[];
    weaknesses: string[];
    reference: string;
  }
> = {
  1: {
    methodology:
      "YouTube チャンネルのエンゲージメント指標のみで政党の勢いを推定し、キューブ則 (Cube Law) を適用して得票率→議席数に変換する。",
    formula:
      "Score(p) = 0.35 × CampaignViews + 0.20 × Likes + 0.10 × Subscribers + 0.10 × ChannelViews + 0.10 × AvgViews + 0.15 × GrowthRate",
    weights: [
      { label: "選挙動画視聴数", value: 0.35, description: "直近の選挙関連動画の合計視聴数" },
      { label: "いいね数", value: 0.2, description: "動画に対するいいね数の合計" },
      { label: "チャンネル登録者", value: 0.1, description: "政党公式チャンネルの登録者数" },
      { label: "チャンネル総視聴", value: 0.1, description: "チャンネル全体の累計視聴数" },
      { label: "平均視聴数", value: 0.1, description: "直近動画の平均視聴回数" },
      { label: "成長率", value: 0.15, description: "登録者数・視聴数の直近成長率" },
    ],
    parameters: [
      { label: "議席変換", value: "キューブ則 (Cube Law): seats ∝ (vote_share)^n" },
      { label: "最適指数 n", value: "2.5〜3.0 (2017/2021/2024 年選挙から校正)" },
      { label: "時間重み", value: "指数減衰 λ=0.05 (直近データを重視)" },
      { label: "候補者上限", value: "実際の立候補者数で議席キャップ" },
    ],
    strengths: [
      "リアルタイム性が高い（日次更新可能）",
      "有権者の関心・熱量を直接反映",
      "データ取得が自動化しやすい",
    ],
    weaknesses: [
      "YouTube 利用層に偏りがある（若年層中心）",
      "組織票の動向を捕捉できない",
      "bot や広告による視聴数操作リスク",
    ],
    reference: "youtube-election-analysis-2026 / Model 1: YouTube Engagement Only",
  },
  2: {
    methodology:
      "モデル 1 のエンゲージメントスコアに、コメント欄の感情分析 (Sentiment) を加味して補正。ポジティブな世論はスコアを押し上げ、ネガティブは押し下げる。",
    formula:
      "AdjScore(p) = Score_M1(p) × (1 + 0.3 × SentimentAdj(p))\nSentimentAdj = positive_ratio − negative_ratio  (範囲: −1.0 〜 +1.0)",
    weights: [
      { label: "M1 エンゲージメント", value: 0.7, description: "モデル 1 の基本スコアを主軸とする" },
      { label: "センチメント補正", value: 0.3, description: "コメント感情分析による上下調整" },
    ],
    parameters: [
      { label: "感情分析手法", value: "コメント文のポジティブ/ニュートラル/ネガティブ三値分類" },
      { label: "補正係数", value: "0.3 (±30% の範囲で調整)" },
      { label: "サンプルサイズ", value: "政党あたり 50〜300 コメント" },
      { label: "議席変換", value: "キューブ則 (M1 と同じ)" },
    ],
    strengths: [
      "視聴「質」を反映（アンチ動画の大量視聴を割り引ける）",
      "炎上 vs 好意的バズを区別できる",
    ],
    weaknesses: [
      "日本語感情分析の精度に依存",
      "皮肉・風刺の解釈が困難",
      "コメント欄が閉鎖されたチャンネルは分析不可",
    ],
    reference: "youtube-election-analysis-2026 / Model 2: Engagement + Sentiment",
  },
  3: {
    methodology:
      "世論調査データを主信号 (75%) とし、YouTube のモメンタム指標を補正信号 (25%) として融合。時間減衰関数で直近の調査を重視する。",
    formula:
      "Blend(p) = 0.75 × PollingAvg(p) + 0.25 × YT_Momentum(p)\nPollingAvg = Σ(poll_i × e^{−λ×Δt_i}) / Σe^{−λ×Δt_i}\nMomentum Clamp: ±10%",
    weights: [
      { label: "世論調査", value: 0.75, description: "時間加重平均した政党支持率" },
      { label: "YouTube 勢い", value: 0.25, description: "直近の視聴数増加率・エンゲージメント変化" },
    ],
    parameters: [
      { label: "時間減衰 λ", value: "0.05 / 日 (直近 7 日間が支配的)" },
      { label: "モメンタム制限", value: "±10% クランプ（急激な揺れを抑制）" },
      { label: "世論調査ソース", value: "NHK, 朝日, 読売, 毎日, 共同, 日経" },
      { label: "議席変換", value: "ドント式 (比例) + キューブ則 (小選挙区)" },
    ],
    strengths: [
      "世論調査の安定性と YouTube のリアルタイム性を両立",
      "モメンタムクランプで異常値の影響を抑制",
      "歴史的に世論調査は信頼性が高い",
    ],
    weaknesses: [
      "世論調査の公開が遅れると予測が遅延",
      "調査間のサンプルバイアスの差異",
      "無党派層の動向を十分に反映できない",
    ],
    reference: "youtube-election-analysis-2026 / Model 3: Polling + YouTube Momentum",
  },
  4: {
    methodology:
      "モデル 1〜3 の加重平均アンサンブル。世論調査を含むモデル 3 に最大の重みを置き、YouTube 単体モデルは補助的に利用する。",
    formula:
      "Ensemble(p) = 0.15 × M1(p) + 0.15 × M2(p) + 0.70 × M3(p)",
    weights: [
      { label: "M1: YouTube エンゲージ", value: 0.15, description: "YouTube 視聴データのみの基本予測" },
      { label: "M2: YouTube + 感情", value: 0.15, description: "感情分析で補正した YouTube 予測" },
      { label: "M3: 世論調査 + YouTube", value: 0.70, description: "世論調査主軸の融合予測" },
    ],
    parameters: [
      { label: "アンサンブル手法", value: "線形加重平均" },
      { label: "重み決定基準", value: "過去選挙 (2017, 2021, 2024) のバックテスト MSE 最小化" },
      { label: "議席合計制約", value: "465 議席 (小選挙区 289 + 比例 176)" },
      { label: "候補者上限適用", value: "政党別の実際の立候補者数でキャップ" },
    ],
    strengths: [
      "単一モデルのバイアスを平滑化",
      "バックテストで重みを校正済み",
      "世論調査の安定性を維持しつつ YouTube の速報性を取り込む",
    ],
    weaknesses: [
      "構成モデル全てが同方向に誤る場合は補正できない",
      "重みが固定で、状況に応じた動的調整はしない",
    ],
    reference: "youtube-election-analysis-2026 / Model 4: Ensemble (M1–M3)",
  },
  5: {
    methodology:
      "ニュース記事の報道量・論調・メディア信頼度を組み合わせた予測。信頼度スコアで記事を重み付けし、時間減衰（半減期 10 日）を適用。世論調査を主錨 (45%) として使用。",
    formula:
      "NewsScore(p) = Σ(article_i × credibility_i × tone_i × e^{−0.069×Δt_i})\nFinal(p) = 0.45 × Polling + 0.25 × NewsScore + 0.15 × MediaMentions + 0.15 × CoverageVolume",
    weights: [
      { label: "世論調査", value: 0.45, description: "支持率データを最重要シグナルとして使用" },
      { label: "ニューススコア", value: 0.25, description: "信頼度×論調で加重した報道評価" },
      { label: "メディア言及数", value: 0.15, description: "政党・候補者が言及された頻度" },
      { label: "報道量", value: 0.15, description: "記事数ベースのカバレッジ量" },
    ],
    parameters: [
      { label: "信頼度スコア", value: "NHK: 4.5 / 朝日: 4.2 / 読売: 4.3 / 毎日: 4.0 / 産経: 3.8 ..." },
      { label: "時間半減期", value: "10 日 (λ = ln2/10 ≈ 0.069)" },
      { label: "PV 基準", value: "1,000 PV 以上の記事のみ対象" },
      { label: "議席変換", value: "ドント式 (比例) + 修正キューブ則 (小選挙区)" },
    ],
    strengths: [
      "メディア報道の量と質の両面を反映",
      "信頼度スコアでタブロイド vs 全国紙を差別化",
      "世論調査で錨を打つため大きな外れを防止",
    ],
    weaknesses: [
      "メディアバイアスの完全な除去は困難",
      "速報記事と分析記事の区別が曖昧",
      "地方紙のカバレッジが不足",
    ],
    reference: "youtube-election-analysis-2026 / Model 5: News-Driven Approach",
  },
  6: {
    methodology:
      "YouTube 系モデル (M4) とニュース系モデル (M5) を統合。FiveThirtyEight 手法に倣い「世論調査アンカリング」を適用し、世論調査からの乖離を最大 30% に制限。",
    formula:
      "Raw(p) = 0.55 × M4(p) + 0.45 × M5(p)\nAnchored(p) = PollingBaseline(p) + clamp(Raw(p) − PollingBaseline(p), −0.30, +0.30)",
    weights: [
      { label: "M4: YouTube アンサンブル", value: 0.55, description: "YouTube 3 モデルの統合結果" },
      { label: "M5: ニュースベース", value: 0.45, description: "ニュース記事ベースの予測" },
    ],
    parameters: [
      { label: "世論調査アンカリング", value: "乖離を ±30% に制限 (FiveThirtyEight 方式)" },
      { label: "ベースライン", value: "最新 3 回の世論調査平均" },
      { label: "議席変換", value: "ドント式 + キューブ則" },
      { label: "候補者キャップ", value: "最大剰余法で余剰議席を再配分" },
    ],
    strengths: [
      "YouTube とニュースの異なる情報源を網羅",
      "アンカリングで世論調査からの極端な逸脱を防止",
      "FiveThirtyEight で実績のある手法を応用",
    ],
    weaknesses: [
      "世論調査が大きく外れた場合、アンカリングが逆効果",
      "YouTube とニュースが同じバイアスを共有する可能性",
    ],
    reference: "youtube-election-analysis-2026 / Model 6: Combined Ensemble with Polling Anchor",
  },
  7: {
    methodology:
      "289 小選挙区それぞれをボトムアップで分析。過去の選挙結果から算出した「パルチザン・リーン」を基盤に、世論調査の全国スウィング、候補者経験、現職優位、YouTube スコア、ニュース言及数を加重合算する。",
    formula:
      "District(d,p) = 0.35 × PartisanLean + 0.25 × PollingSwing + 0.10 × CandidateExp + 0.05 × Incumbency + 0.15 × YouTubeScore + 0.10 × NewsMentions",
    weights: [
      { label: "パルチザン・リーン", value: 0.35, description: "過去選挙 (2024) の小選挙区得票率から算出した政党傾斜" },
      { label: "世論調査スウィング", value: 0.25, description: "全国世論調査の変動を選挙区に適用" },
      { label: "候補者経験", value: 0.10, description: "現職/元職/新人の分類に基づく経験値" },
      { label: "現職ボーナス", value: 0.05, description: "日本の RD 研究に基づく控えめな現職優位" },
      { label: "YouTube スコア", value: 0.15, description: "選挙区関連の YouTube エンゲージメント" },
      { label: "ニュース言及数", value: 0.10, description: "選挙区・候補者のメディア言及頻度" },
    ],
    parameters: [
      { label: "パルチザン・リーン算出", value: "2024 年衆院選の小選挙区得票率を基準" },
      { label: "中道改革連合の扱い", value: "旧立民 + 公明の候補を統合して算出" },
      { label: "比例ブロック", value: "ドント式で 11 ブロック × 政党を算出" },
      { label: "現職ボーナス値", value: "0.05 (日本の選挙研究で推定された保守的な値)" },
    ],
    strengths: [
      "選挙区ごとの事情を最も精緻に反映",
      "候補者個人の強さを考慮できる",
      "全 6 種のシグナルを統合した最も包括的なモデル",
    ],
    weaknesses: [
      "データ要求量が最大（289 選挙区 × 複数指標）",
      "パルチザン・リーンの基準選挙が古い場合、精度低下",
      "候補者の個人的事情（スキャンダル等）は反映困難",
    ],
    reference: "youtube-election-analysis-2026 / Model 7: Bottom-Up District Analysis",
  },
};

interface ModelDetailCardProps {
  model: ModelComparisonEntry;
}

export default function ModelDetailCard({ model }: ModelDetailCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const detail = MODEL_DETAILS[model.model_number];

  const totalSeats = Object.values(model.predictions).reduce((a, b) => a + b, 0);
  const sortedParties = Object.entries(model.predictions).sort(([, a], [, b]) => b - a);
  const topParty = sortedParties[0];

  return (
    <div
      className={`bg-white border rounded-lg transition-all duration-200 ${
        isOpen ? "border-blue-300 shadow-md col-span-1 md:col-span-2 lg:col-span-3" : "border-gray-200 hover:border-blue-200 hover:shadow-sm"
      }`}
    >
      {/* Clickable Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full text-left p-5 focus:outline-none focus:ring-2 focus:ring-blue-200 rounded-lg"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-1 rounded">
              M{model.model_number}
            </span>
            <h3 className="font-bold text-sm">{model.model_name}</h3>
          </div>
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${
              isOpen ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        <p className="text-xs text-gray-600 mt-2">{model.description}</p>
        <div className="text-xs text-gray-500 mt-1">
          データソース: {model.data_sources}
        </div>
        <div className="border-t mt-3 pt-3 flex flex-wrap gap-4">
          <div className="text-sm">
            <span className="text-gray-500">予測総議席 </span>
            <span className="font-bold">{totalSeats}</span>
          </div>
          {topParty && (
            <div className="text-sm flex items-center gap-1">
              <span className="text-gray-500">第一党 </span>
              <span
                className="w-2 h-2 rounded-full inline-block"
                style={{ backgroundColor: PARTY_COLORS[topParty[0]] || "#999" }}
              />
              <span className="font-bold">
                {PARTY_NAMES[topParty[0]] || topParty[0]} ({topParty[1]}議席)
              </span>
            </div>
          )}
        </div>
      </button>

      {/* Expandable Detail */}
      {isOpen && detail && (
        <div className="px-5 pb-5 border-t border-gray-100">
          {/* Methodology */}
          <div className="mt-4">
            <h4 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-1.5">
              <span className="text-blue-500">&#9432;</span> 手法
            </h4>
            <p className="text-sm text-gray-600 leading-relaxed">{detail.methodology}</p>
          </div>

          {/* Formula */}
          <div className="mt-4">
            <h4 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-1.5">
              <span className="text-green-500">&#402;</span> 計算式
            </h4>
            <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs font-mono text-gray-700 overflow-x-auto whitespace-pre-wrap">
              {detail.formula}
            </pre>
          </div>

          {/* Weights */}
          <div className="mt-4">
            <h4 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-1.5">
              <span className="text-orange-500">&#9878;</span> 重み配分
            </h4>
            <div className="space-y-2">
              {detail.weights.map((w) => (
                <div key={w.label}>
                  <div className="flex items-center justify-between text-xs mb-0.5">
                    <span className="font-medium text-gray-700">{w.label}</span>
                    <span className="font-bold text-blue-600">{(w.value * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-gray-100 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-blue-500 transition-all duration-500"
                        style={{ width: `${w.value * 100}%` }}
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">{w.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Parameters */}
          <div className="mt-4">
            <h4 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-1.5">
              <span className="text-purple-500">&#9881;</span> パラメータ
            </h4>
            <div className="bg-gray-50 rounded-lg divide-y divide-gray-200">
              {detail.parameters.map((param) => (
                <div key={param.label} className="px-3 py-2 flex flex-col sm:flex-row sm:items-center gap-1">
                  <span className="text-xs font-medium text-gray-500 sm:w-40 flex-shrink-0">
                    {param.label}
                  </span>
                  <span className="text-xs text-gray-700">{param.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Strengths & Weaknesses */}
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-bold text-green-700 mb-2">強み</h4>
              <ul className="space-y-1">
                {detail.strengths.map((s, i) => (
                  <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                    <span className="text-green-500 mt-0.5">&#10003;</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-bold text-red-700 mb-2">弱み</h4>
              <ul className="space-y-1">
                {detail.weaknesses.map((w, i) => (
                  <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                    <span className="text-red-500 mt-0.5">&#10007;</span>
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Party Breakdown Mini-bar */}
          <div className="mt-4">
            <h4 className="text-sm font-bold text-gray-700 mb-2">政党別予測議席</h4>
            <div className="space-y-1.5">
              {sortedParties.map(([pid, seats]) => (
                <div key={pid} className="flex items-center gap-2">
                  <span className="text-xs w-14 text-right font-medium">
                    {PARTY_NAMES[pid] || pid}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                    <div
                      className="h-full rounded-full flex items-center justify-end pr-1.5"
                      style={{
                        backgroundColor: PARTY_COLORS[pid] || "#999",
                        width: `${Math.max((seats / totalSeats) * 100, 3)}%`,
                        opacity: 0.85,
                      }}
                    >
                      <span className="text-[10px] font-bold text-white drop-shadow">
                        {seats}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reference */}
          <div className="mt-4 pt-3 border-t border-gray-100">
            <p className="text-[10px] text-gray-400">
              参考: {detail.reference}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
