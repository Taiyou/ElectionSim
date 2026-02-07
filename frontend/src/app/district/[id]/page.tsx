import {
  fetchDistrictDetail,
  fetchDistrictPrediction,
  fetchDistrictHistory,
} from "@/lib/api-client";
import ConfidenceBadge from "@/components/prediction/ConfidenceBadge";
import PartyBadge from "@/components/prediction/PartyBadge";
import Link from "next/link";

export const revalidate = 1200;

export default async function DistrictPage({
  params,
}: {
  params: { id: string };
}) {
  let district;
  let prediction;
  let history;

  try {
    [district, prediction, history] = await Promise.all([
      fetchDistrictDetail(params.id),
      fetchDistrictPrediction(params.id),
      fetchDistrictHistory(params.id),
    ]);
  } catch {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Link href="/" className="text-blue-600 hover:underline text-sm">
          &larr; ダッシュボードに戻る
        </Link>
        <h1 className="text-2xl font-bold mt-4">選挙区: {params.id}</h1>
        <p className="text-gray-500 mt-2">データが見つかりません</p>
      </div>
    );
  }

  let keyFactors: string[] = [];
  try {
    keyFactors = JSON.parse(prediction.key_factors);
  } catch {
    /* empty */
  }

  let rankings: Array<{ rank: number; name: string; party_id: string }> = [];
  try {
    rankings = JSON.parse(prediction.candidate_rankings);
  } catch {
    /* empty */
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500 mb-4">
        <Link href="/" className="hover:underline">
          ホーム
        </Link>
        {" > "}
        <span>{district.prefecture}</span>
        {" > "}
        <span className="font-semibold text-gray-900 dark:text-gray-100">
          {district.name}
        </span>
      </nav>

      {/* District Info */}
      <h1 className="text-2xl font-bold">{district.name}</h1>
      <p className="text-gray-500 mt-1">{district.area_description}</p>

      {/* Prediction Result */}
      <section className="mt-6 bg-white dark:bg-gray-800 border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">AI予測結果</h2>
          <ConfidenceBadge
            confidence={prediction.confidence}
            score={prediction.confidence_score}
          />
        </div>

        <p className="text-gray-700 dark:text-gray-300">
          {prediction.analysis_summary}
        </p>

        {keyFactors.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-gray-500 mb-2">決定要因</h3>
            <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400">
              {keyFactors.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* Candidate Rankings */}
      {rankings.length > 0 && (
        <section className="mt-6">
          <h2 className="text-lg font-bold mb-3">候補者予測順位</h2>
          <div className="space-y-2">
            {rankings.map((r) => (
              <div
                key={r.rank}
                className="flex items-center gap-3 border rounded-lg p-3 bg-white dark:bg-gray-800"
              >
                <span className="text-lg font-bold text-gray-400 w-8">
                  {r.rank}
                </span>
                <span className="font-semibold">{r.name}</span>
                <PartyBadge partyId={r.party_id} />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Candidates */}
      {district.candidates && district.candidates.length > 0 && (
        <section className="mt-6">
          <h2 className="text-lg font-bold mb-3">立候補者一覧</h2>
          <div className="space-y-2">
            {district.candidates.map((c) => (
              <div
                key={c.id}
                className="flex items-center gap-3 border rounded-lg p-3 bg-white dark:bg-gray-800"
              >
                <PartyBadge partyId={c.party_id} />
                <div>
                  <span className="font-semibold">{c.name}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    {c.is_incumbent ? "現職" : "新人"}
                    {c.previous_wins > 0 && ` / 当選${c.previous_wins}回`}
                    {c.age && ` / ${c.age}歳`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* History */}
      {history.length > 0 && (
        <section className="mt-6">
          <h2 className="text-lg font-bold mb-3">予測推移</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3">日時</th>
                  <th className="text-left py-2 px-3">予測政党</th>
                  <th className="text-left py-2 px-3">確信度</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i} className="border-b">
                    <td className="py-2 px-3">
                      {new Date(h.created_at).toLocaleString("ja-JP")}
                    </td>
                    <td className="py-2 px-3">
                      <PartyBadge partyId={h.predicted_winner_party_id} />
                    </td>
                    <td className="py-2 px-3">
                      <ConfidenceBadge
                        confidence={h.confidence as "high" | "medium" | "low"}
                        score={h.confidence_score}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
