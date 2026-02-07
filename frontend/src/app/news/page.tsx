import { fetchNewsSummary } from "@/lib/api-client";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import NewsDailyChart from "@/components/charts/NewsDailyChart";
import PollingChart from "@/components/charts/PollingChart";

export const revalidate = 1200;

export default async function NewsPage() {
  let data;

  try {
    data = await fetchNewsSummary();
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-4">ニュース記事分析</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <p className="text-yellow-800">
            ニュースデータを取得できません。バックエンドAPIを確認してください。
          </p>
        </div>
      </div>
    );
  }

  const sortedSources = Object.entries(data.source_breakdown)
    .sort(([, a], [, b]) => b - a);

  const sortedPartyCoverage = Object.entries(data.party_coverage_counts)
    .sort(([, a], [, b]) => b - a);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <section className="mb-10">
        <h1 className="text-3xl font-bold mb-2">ニュース記事分析</h1>
        <p className="text-gray-500 text-sm">
          選挙関連ニュース記事の報道量・論調・世論調査データ分析
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <StatCard label="記事総数" value={data.total_articles.toLocaleString()} />
          <StatCard label="総PV" value={formatNumber(data.total_page_views)} />
          <StatCard label="メディア数" value={`${data.total_sources}`} />
          <StatCard
            label="平均論調"
            value={data.avg_tone.toFixed(3)}
            highlight={data.avg_tone > 0}
          />
        </div>
      </section>

      {/* Daily Coverage Trend */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">日次報道量トレンド</h2>
        <NewsDailyChart dailyCoverage={data.daily_coverage} />
      </section>

      {/* Polling Trends */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">世論調査推移</h2>
        <PollingChart polling={data.polling} />
      </section>

      {/* Source Breakdown & Party Coverage */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
        <section>
          <h2 className="text-xl font-bold mb-4">メディア別記事数</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="space-y-2">
              {sortedSources.map(([source, count]) => {
                const maxCount = sortedSources[0]?.[1] || 1;
                return (
                  <div key={source} className="flex items-center gap-3">
                    <span className="text-sm w-28 truncate">{source}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-indigo-500 flex items-center justify-end pr-2"
                        style={{
                          width: `${Math.max((count / maxCount) * 100, 8)}%`,
                          opacity: 0.8,
                        }}
                      >
                        <span className="text-xs font-bold text-white drop-shadow">{count}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-bold mb-4">政党別報道量</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="space-y-2">
              {sortedPartyCoverage.map(([partyId, count]) => {
                const maxCount = sortedPartyCoverage[0]?.[1] || 1;
                return (
                  <div key={partyId} className="flex items-center gap-3">
                    <span className="text-sm w-16">{PARTY_NAMES[partyId] || partyId}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                      <div
                        className="h-full rounded-full flex items-center justify-end pr-2"
                        style={{
                          backgroundColor: PARTY_COLORS[partyId] || "#999",
                          width: `${Math.max((count / maxCount) * 100, 8)}%`,
                          opacity: 0.8,
                        }}
                      >
                        <span className="text-xs font-bold text-white drop-shadow">{count}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      </div>

      {/* Top Articles */}
      <section>
        <h2 className="text-xl font-bold mb-4">注目記事 (PV上位)</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200 rounded-lg text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">メディア</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">タイトル</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">PV</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">論調</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">信頼度</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">政党</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.articles.slice(0, 20).map((article) => (
                <tr key={article.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap">{article.source}</td>
                  <td className="px-4 py-3 max-w-xs truncate">{article.title}</td>
                  <td className="px-4 py-3 text-right">{article.page_views.toLocaleString()}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs ${
                        article.tone_score > 0.2
                          ? "bg-green-100 text-green-700"
                          : article.tone_score < -0.2
                            ? "bg-red-100 text-red-700"
                            : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {article.tone_score > 0 ? "+" : ""}{article.tone_score.toFixed(2)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">{article.credibility_score.toFixed(1)}</td>
                  <td className="px-4 py-3 text-center">
                    {article.party_mention && (
                      <span
                        className="px-1.5 py-0.5 rounded text-xs text-white"
                        style={{
                          backgroundColor: PARTY_COLORS[article.party_mention] || "#999",
                        }}
                      >
                        {PARTY_NAMES[article.party_mention] || article.party_mention}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
          ? "bg-green-50 border-green-200"
          : "bg-white border-gray-200"
      }`}
    >
      <p className={`text-2xl font-bold ${highlight ? "text-green-600" : ""}`}>
        {value}
      </p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}

function formatNumber(num: number): string {
  if (num >= 100000000) return `${(num / 100000000).toFixed(1)}億`;
  if (num >= 10000) return `${(num / 10000).toFixed(1)}万`;
  return num.toLocaleString();
}
