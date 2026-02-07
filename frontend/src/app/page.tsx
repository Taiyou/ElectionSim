import Link from "next/link";
import {
  fetchPredictionSummary,
  fetchBattleground,
  fetchYouTubeSummary,
  fetchNewsSummary,
  fetchPersonaSummary,
} from "@/lib/api-client";
import SeatDistribution from "@/components/charts/SeatDistribution";
import DistrictCard from "@/components/prediction/DistrictCard";

export const revalidate = 1200;

export default async function DashboardPage() {
  let summary;
  let battleground;
  let ytSummary;
  let newsSummary;
  let personaSummary;

  try {
    [summary, battleground] = await Promise.all([
      fetchPredictionSummary(),
      fetchBattleground(),
    ]);
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-4">衆議院選挙 AI予測ダッシュボード</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <p className="text-yellow-800">
            バックエンドAPIに接続できません。サーバーが起動しているか確認してください。
          </p>
          <p className="text-sm text-yellow-600 mt-2">
            <code>cd backend && uvicorn app.main:app --reload</code>
          </p>
        </div>
      </div>
    );
  }

  // Fetch YouTube, news, and persona summaries (non-blocking, optional)
  try {
    [ytSummary, newsSummary, personaSummary] = await Promise.all([
      fetchYouTubeSummary(),
      fetchNewsSummary(),
      fetchPersonaSummary(),
    ]);
  } catch {
    // These are optional data sources - dashboard still works without them
  }

  const totalSeats = summary.party_seats.reduce((acc, p) => acc + p.total_seats, 0);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Hero Section */}
      <section className="mb-10">
        <h1 className="text-3xl font-bold mb-2">衆議院選挙 AI予測ダッシュボード</h1>
        <p className="text-gray-500 text-sm">
          最終更新: {summary.updated_at ? new Date(summary.updated_at).toLocaleString("ja-JP") : "未更新"}
          {" | "}バッチID: {summary.batch_id}
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <StatCard label="総議席" value={`${summary.total_seats}`} />
          <StatCard label="予測済み議席" value={`${totalSeats}`} />
          <StatCard label="過半数ライン" value={`${summary.majority_line}`} />
          <StatCard
            label="接戦区数"
            value={`${summary.battleground_count}`}
            highlight
          />
        </div>
      </section>

      {/* Seat Distribution */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">政党別予測議席数</h2>
        {summary.party_seats.length > 0 ? (
          <SeatDistribution
            partySeats={summary.party_seats}
            majorityLine={summary.majority_line}
          />
        ) : (
          <p className="text-gray-500">予測データがまだありません</p>
        )}
      </section>

      {/* Candidate Stats */}
      {summary.candidate_stats && (
        <section className="mb-10">
          <h2 className="text-xl font-bold mb-4">候補者統計</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <StatCard
              label="総候補者数"
              value={`${summary.candidate_stats.total_candidates}`}
            />
            <StatCard
              label="選挙区数"
              value={`${summary.candidate_stats.total_districts}`}
            />
            <StatCard
              label="現職候補者"
              value={`${summary.candidate_stats.incumbent_count}`}
            />
            <StatCard
              label="重複立候補"
              value={`${summary.candidate_stats.dual_candidacy_count}`}
            />
          </div>
          <div className="bg-white dark:bg-gray-800 border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-500 mb-3">政党別候補者数</h3>
            <div className="space-y-2">
              {summary.candidate_stats.party_breakdown.map((party) => (
                <div key={party.party_id} className="flex items-center gap-3">
                  <div
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: party.color }}
                  />
                  <span className="text-sm w-16">{party.name_short}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                    <div
                      className="h-full rounded-full flex items-center justify-end pr-2"
                      style={{
                        backgroundColor: party.color,
                        width: `${Math.max(
                          (party.count / summary.candidate_stats!.total_candidates) * 100,
                          8
                        )}%`,
                        opacity: 0.8,
                      }}
                    >
                      <span className="text-xs font-bold text-white drop-shadow">
                        {party.count}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Confidence Distribution */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">確信度分布</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-green-700">
              {summary.confidence_distribution.high || 0}
            </p>
            <p className="text-sm text-green-600">高確信</p>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-yellow-700">
              {summary.confidence_distribution.medium || 0}
            </p>
            <p className="text-sm text-yellow-600">中確信</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-red-700">
              {summary.confidence_distribution.low || 0}
            </p>
            <p className="text-sm text-red-600">低確信（接戦）</p>
          </div>
        </div>
      </section>

      {/* Data Sources Summary */}
      {(ytSummary || newsSummary || personaSummary) && (
        <section className="mb-10">
          <h2 className="text-xl font-bold mb-4">データソース概要</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {ytSummary && (
              <Link href="/youtube" className="block">
                <div className="bg-red-50 border border-red-200 rounded-lg p-5 hover:shadow-md transition">
                  <h3 className="font-bold text-red-700 mb-2">YouTube分析</h3>
                  <div className="space-y-1 text-sm text-gray-600">
                    <p>分析動画数: <span className="font-bold">{ytSummary.total_videos.toLocaleString()}</span></p>
                    <p>チャンネル数: <span className="font-bold">{ytSummary.total_channels}</span></p>
                    <p>平均センチメント: <span className={`font-bold ${ytSummary.avg_sentiment >= 0 ? "text-green-600" : "text-red-600"}`}>{ytSummary.avg_sentiment.toFixed(3)}</span></p>
                  </div>
                  <p className="text-xs text-red-500 mt-3">詳細を見る →</p>
                </div>
              </Link>
            )}
            {newsSummary && (
              <Link href="/news" className="block">
                <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-5 hover:shadow-md transition">
                  <h3 className="font-bold text-indigo-700 mb-2">ニュース記事分析</h3>
                  <div className="space-y-1 text-sm text-gray-600">
                    <p>記事総数: <span className="font-bold">{newsSummary.total_articles.toLocaleString()}</span></p>
                    <p>メディア数: <span className="font-bold">{newsSummary.total_sources}</span></p>
                    <p>平均論調: <span className={`font-bold ${newsSummary.avg_tone >= 0 ? "text-green-600" : "text-red-600"}`}>{newsSummary.avg_tone.toFixed(3)}</span></p>
                  </div>
                  <p className="text-xs text-indigo-500 mt-3">詳細を見る →</p>
                </div>
              </Link>
            )}
            {personaSummary && (
              <Link href="/personas" className="block">
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-5 hover:shadow-md transition">
                  <h3 className="font-bold text-purple-700 mb-2">ペルソナ分析</h3>
                  <div className="space-y-1 text-sm text-gray-600">
                    <p>ペルソナ類型: <span className="font-bold">{personaSummary.total_archetypes}</span></p>
                    <p>対象都道府県: <span className="font-bold">{personaSummary.total_prefectures}</span></p>
                    <p>平均投票率: <span className="font-bold">{(personaSummary.avg_turnout_probability * 100).toFixed(1)}%</span></p>
                  </div>
                  <p className="text-xs text-purple-500 mt-3">詳細を見る →</p>
                </div>
              </Link>
            )}
            <Link href="/models" className="block">
              <div className="bg-green-50 border border-green-200 rounded-lg p-5 hover:shadow-md transition">
                <h3 className="font-bold text-green-700 mb-2">予測モデル比較</h3>
                <div className="space-y-1 text-sm text-gray-600">
                  <p>モデル数: <span className="font-bold">7</span></p>
                  <p>YouTube / ニュース / 世論調査</p>
                  <p>アンサンブル + 選挙区分析</p>
                </div>
                <p className="text-xs text-green-500 mt-3">詳細を見る →</p>
              </div>
            </Link>
          </div>
        </section>
      )}

      {/* Battleground Districts */}
      <section>
        <h2 className="text-xl font-bold mb-4">注目の接戦区</h2>
        {battleground.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {battleground.slice(0, 9).map((pred) => (
              <DistrictCard key={pred.district_id} prediction={pred} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500">接戦区データがまだありません</p>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-lg p-4 text-center border ${
        highlight
          ? "bg-red-50 border-red-200"
          : "bg-white dark:bg-gray-800 border-gray-200"
      }`}
    >
      <p className={`text-2xl font-bold ${highlight ? "text-red-600" : ""}`}>
        {value}
      </p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}
