import { fetchBattleground } from "@/lib/api-client";
import DistrictCard from "@/components/prediction/DistrictCard";

export const revalidate = 1200;

export default async function BattlegroundPage() {
  let predictions;

  try {
    predictions = await fetchBattleground();
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-4">接戦区一覧</h1>
        <p className="text-gray-500">データを取得できませんでした</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">接戦区一覧</h1>
      <p className="text-gray-500 text-sm mb-6">
        確信度が「低」または「中」の選挙区（{predictions.length}区）
      </p>

      {predictions.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {predictions.map((pred) => (
            <DistrictCard key={pred.district_id} prediction={pred} />
          ))}
        </div>
      ) : (
        <p className="text-gray-500">接戦区データがまだありません</p>
      )}
    </div>
  );
}
