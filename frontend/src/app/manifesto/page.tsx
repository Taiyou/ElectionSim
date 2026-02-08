import { fetchManifestoSummary, fetchProportionalBlocks } from "@/lib/api-client";
import ManifestoClient from "./ManifestoClient";

export const revalidate = 1200;

export default async function ManifestoPage() {
  let data;
  let blocks;

  try {
    [data, blocks] = await Promise.all([
      fetchManifestoSummary(),
      fetchProportionalBlocks().catch(() => []),
    ]);
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-4">マニフェスト分析</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <p className="text-yellow-800">
            マニフェストデータを取得できません。バックエンドAPIを確認してください。
          </p>
        </div>
      </div>
    );
  }

  return <ManifestoClient data={data} blocks={blocks} />;
}
