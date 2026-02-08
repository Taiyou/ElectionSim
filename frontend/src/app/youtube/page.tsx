import { fetchYouTubeSummary } from "@/lib/api-client";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import YouTubeDailyChart from "@/components/charts/YouTubeDailyChart";
import SentimentChart from "@/components/charts/SentimentChart";

export const revalidate = 1200;

export default async function YouTubePage() {
  let data;

  try {
    data = await fetchYouTubeSummary();
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-4">YouTube分析</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <p className="text-yellow-800">
            YouTube分析データを取得できません。バックエンドAPIを確認してください。
          </p>
        </div>
      </div>
    );
  }

  const sortedPartyVideos = Object.entries(data.party_video_counts)
    .sort(([, a], [, b]) => b - a);

  const sortedIssues = Object.entries(data.issue_distribution)
    .sort(([, a], [, b]) => b - a);

  // Build party_id -> channel_url map for video link fallback
  const partyChannelUrl: Record<string, string> = {};
  for (const ch of data.channels) {
    if (ch.party_id && ch.channel_url) {
      partyChannelUrl[ch.party_id] = ch.channel_url;
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <section className="mb-10">
        <h1 className="text-3xl font-bold mb-2">YouTube選挙分析</h1>
        <p className="text-gray-500 text-sm">
          選挙関連YouTube動画のエンゲージメント・センチメント分析
        </p>
        {data.last_updated && (
          <p className="text-xs text-gray-400 mt-1">
            最終データ更新: {new Date(data.last_updated).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })}
          </p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <StatCard label="分析動画数" value={data.total_videos.toLocaleString()} />
          <StatCard label="総視聴回数" value={formatNumber(data.total_views)} />
          <StatCard label="チャンネル数" value={`${data.total_channels}`} />
          <StatCard
            label="平均センチメント"
            value={data.avg_sentiment.toFixed(3)}
            highlight={data.avg_sentiment > 0}
          />
        </div>
      </section>

      {/* Daily Trend */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">日次動画投稿トレンド</h2>
        <YouTubeDailyChart dailyStats={data.daily_stats} />
      </section>

      {/* Channels */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">政党別チャンネル統計</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200 rounded-lg text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">チャンネル</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">登録者</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">動画数</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">総視聴</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">平均視聴</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">成長率</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.channels.map((ch) => {
                const channelLink = ch.channel_url || `https://www.youtube.com/channel/${ch.channel_id}`;
                return (
                  <tr key={ch.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <a
                        href={channelLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        {ch.party_id && (
                          <span
                            className="w-3 h-3 rounded-full inline-block flex-shrink-0"
                            style={{ backgroundColor: PARTY_COLORS[ch.party_id] || "#999" }}
                          />
                        )}
                        <svg className="w-4 h-4 flex-shrink-0 text-red-500" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/>
                          <path d="M9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="white"/>
                        </svg>
                        <span>{ch.channel_name}</span>
                      </a>
                    </td>
                    <td className="px-4 py-3 text-right">{ch.subscriber_count.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">{ch.video_count.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">{formatNumber(ch.total_views)}</td>
                    <td className="px-4 py-3 text-right">{ch.recent_avg_views.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={ch.growth_rate >= 0 ? "text-green-600" : "text-red-600"}>
                        {ch.growth_rate >= 0 ? "+" : ""}{(ch.growth_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Sentiment Analysis */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">政党別センチメント分析</h2>
        <SentimentChart sentiments={data.sentiments} />
      </section>

      {/* Party Video Counts & Issue Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
        <section>
          <h2 className="text-xl font-bold mb-4">政党別関連動画数</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="space-y-3">
              {sortedPartyVideos.map(([partyId, count]) => {
                const maxCount = sortedPartyVideos[0]?.[1] || 1;
                return (
                  <div key={partyId} className="flex items-center gap-3">
                    <span className="text-sm w-16">{PARTY_NAMES[partyId] || partyId}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
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

        <section>
          <h2 className="text-xl font-bold mb-4">イシュー別動画分布</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="space-y-3">
              {sortedIssues.map(([issue, count]) => {
                const maxCount = sortedIssues[0]?.[1] || 1;
                return (
                  <div key={issue} className="flex items-center gap-3">
                    <span className="text-sm w-28 truncate">{issue}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-blue-500 flex items-center justify-end pr-2"
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
      </div>

      {/* Recent Top Videos */}
      <section>
        <h2 className="text-xl font-bold mb-4">注目動画 (視聴回数上位)</h2>
        {/* Notice when using sample data */}
        {data.recent_videos.length > 0 && !data.recent_videos[0].video_url && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
            <p className="text-xs text-amber-700">
              現在はサンプルデータを表示しています。リンクは各政党の公式YouTubeチャンネルに遷移します。
              YouTube APIキーを設定すると実際の動画データに更新されます。
            </p>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.recent_videos.slice(0, 10).map((video) => {
            const hasRealUrl = !!video.video_url;
            // Real video URL or fallback to party channel URL
            const videoLink =
              video.video_url ||
              (video.party_mention && partyChannelUrl[video.party_mention]) ||
              `https://www.youtube.com/channel/${video.channel_id}`;
            return (
              <a
                key={video.id}
                href={videoLink}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-white border border-gray-200 rounded-lg p-4 transition-shadow block hover:shadow-md hover:border-gray-300 cursor-pointer"
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-medium line-clamp-2">{video.title}</h3>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${
                      video.sentiment_score > 0.2
                        ? "bg-green-100 text-green-700"
                        : video.sentiment_score < -0.2
                          ? "bg-red-100 text-red-700"
                          : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {video.sentiment_score > 0 ? "+" : ""}{video.sentiment_score.toFixed(2)}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                  <span>{video.view_count.toLocaleString()} 視聴</span>
                  <span>{video.like_count.toLocaleString()} いいね</span>
                  <span>{video.comment_count.toLocaleString()} コメント</span>
                  {video.party_mention && (
                    <span
                      className="px-1.5 py-0.5 rounded text-white"
                      style={{ backgroundColor: PARTY_COLORS[video.party_mention] || "#999" }}
                    >
                      {PARTY_NAMES[video.party_mention] || video.party_mention}
                    </span>
                  )}
                  {!hasRealUrl && (
                    <span className="text-[10px] text-amber-500 flex items-center gap-0.5">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      チャンネルへ
                    </span>
                  )}
                </div>
              </a>
            );
          })}
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
