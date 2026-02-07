import { fetchProportionalBlocks } from "@/lib/api-client";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";

export const revalidate = 1200;

export default async function ProportionalPage() {
  let blocks;

  try {
    blocks = await fetchProportionalBlocks();
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-4">比例代表ブロック</h1>
        <p className="text-gray-500">データを取得できませんでした</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">比例代表ブロック予測</h1>
      <p className="text-gray-500 text-sm mb-6">
        全11比例ブロック・176議席の政党別予測
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {blocks.map(({ block, predictions }) => {
          let prefectures: string[] = [];
          try {
            prefectures = JSON.parse(block.prefectures);
          } catch {
            /* empty */
          }

          return (
            <div
              key={block.id}
              className="border rounded-lg p-5 bg-white dark:bg-gray-800"
            >
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-bold text-lg">{block.name}</h3>
                  <p className="text-xs text-gray-500">
                    {prefectures.join("・")}
                  </p>
                </div>
                <span className="bg-gray-100 dark:bg-gray-700 rounded px-2 py-1 text-sm font-bold">
                  定数 {block.total_seats}
                </span>
              </div>

              {predictions.length > 0 ? (
                <div className="space-y-2">
                  {predictions.map((p) => (
                    <div
                      key={p.party_id}
                      className="flex items-center gap-2"
                    >
                      <span
                        className="inline-block w-3 h-3 rounded-full"
                        style={{
                          backgroundColor: PARTY_COLORS[p.party_id] || "#9E9E9E",
                        }}
                      />
                      <span className="text-sm w-16">
                        {PARTY_NAMES[p.party_id] || p.party_id}
                      </span>
                      <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-4 overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${(p.predicted_seats / block.total_seats) * 100}%`,
                            backgroundColor: PARTY_COLORS[p.party_id] || "#9E9E9E",
                          }}
                        />
                      </div>
                      <span className="text-sm font-bold w-8 text-right">
                        {p.predicted_seats}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">予測データなし</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
