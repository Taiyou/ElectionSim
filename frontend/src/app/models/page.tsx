import { fetchModelComparison } from "@/lib/api-client";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import ModelComparisonChart from "@/components/charts/ModelComparisonChart";
import ModelDetailCard from "@/components/models/ModelDetailCard";

export const revalidate = 1200;

export default async function ModelsPage() {
  let data;

  try {
    data = await fetchModelComparison();
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-4">予測モデル比較</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <p className="text-yellow-800">
            モデル比較データを取得できません。バックエンドAPIを確認してください。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <section className="mb-10">
        <h1 className="text-3xl font-bold mb-2">予測モデル比較</h1>
        <p className="text-gray-500 text-sm">
          7つの予測モデルによる議席予測の比較分析（YouTube・ニュース・世論調査ベース）
        </p>
        <p className="text-gray-400 text-xs mt-1">
          各モデルカードをクリックすると、計算式・重み・パラメータの詳細を確認できます
        </p>
      </section>

      {/* Chart */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">全モデル議席予測比較</h2>
        <ModelComparisonChart data={data} />
      </section>

      {/* Model Descriptions - Expandable Cards */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">モデル説明</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.models.map((model) => (
            <ModelDetailCard key={model.model_number} model={model} />
          ))}
        </div>
      </section>

      {/* Detailed Table */}
      <section>
        <h2 className="text-xl font-bold mb-4">モデル別詳細予測</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200 rounded-lg text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-3 text-left font-medium text-gray-600 sticky left-0 bg-gray-50">
                  モデル
                </th>
                {data.party_ids.map((pid) => (
                  <th key={pid} className="px-3 py-3 text-center font-medium text-gray-600">
                    <span className="flex items-center justify-center gap-1">
                      <span
                        className="w-2 h-2 rounded-full inline-block"
                        style={{ backgroundColor: PARTY_COLORS[pid] || "#999" }}
                      />
                      {PARTY_NAMES[pid] || pid}
                    </span>
                  </th>
                ))}
                <th className="px-3 py-3 text-center font-medium text-gray-600">合計</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.models.map((model) => {
                const total = Object.values(model.predictions).reduce((a, b) => a + b, 0);
                return (
                  <tr key={model.model_number} className="hover:bg-gray-50">
                    <td className="px-3 py-3 whitespace-nowrap font-medium sticky left-0 bg-white">
                      <span className="text-blue-600">M{model.model_number}</span>{" "}
                      {model.model_name}
                    </td>
                    {data.party_ids.map((pid) => {
                      const seats = model.predictions[pid] || 0;
                      return (
                        <td key={pid} className="px-3 py-3 text-center">
                          <span
                            className={`${
                              seats >= data.majority_line ? "font-bold text-red-600" : ""
                            }`}
                          >
                            {seats}
                          </span>
                        </td>
                      );
                    })}
                    <td className="px-3 py-3 text-center font-bold">{total}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
