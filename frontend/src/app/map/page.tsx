import { fetchMapSummary } from "@/lib/api-client";
import JapanMapClient from "@/components/charts/JapanMap";

export const revalidate = 1200;

export default async function MapPage() {
  let prefectureData;

  try {
    prefectureData = await fetchMapSummary();
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-4">選挙区マップ</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <p className="text-yellow-800">
            データを取得できませんでした。バックエンドAPIが起動しているか確認してください。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">選挙区マップ</h1>
      <p className="text-gray-500 text-sm mb-6">
        47都道府県の候補者情報を地図上に表示。色は各都道府県で最も多くの候補者を擁立している政党を示しています。
      </p>
      <JapanMapClient prefectureData={prefectureData} />
    </div>
  );
}
