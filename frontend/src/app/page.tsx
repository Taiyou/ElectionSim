import {
  fetchPredictionSummary,
  fetchBattleground,
} from "@/lib/api-client";
import SeatDistribution from "@/components/charts/SeatDistribution";
import DistrictCard from "@/components/prediction/DistrictCard";

export const revalidate = 1200;

export default async function DashboardPage() {
  let summary;
  let battleground;

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
