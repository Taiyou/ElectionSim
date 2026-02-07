import { fetchPrompts } from "@/lib/api-client";

export const revalidate = 3600;

export default async function HowItWorksPage() {
  let prompts: Record<string, { name: string; description: string; template: string }> | null = null;

  try {
    prompts = (await fetchPrompts()) as Record<
      string,
      { name: string; description: string; template: string }
    >;
  } catch {
    // API not available
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">仕組み</h1>
      <p className="text-gray-500 text-sm mb-8">
        本システムの予測メカニズムと使用しているプロンプトを公開しています
      </p>

      {/* Flow */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">予測フロー</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StepCard
            step={1}
            title="データ収集"
            description="Perplexity APIでニュース・世論調査を、Grok APIでX(Twitter)の投稿をそれぞれ並列で収集・分析します。"
            ai="Perplexity + Grok"
          />
          <StepCard
            step={2}
            title="統合分析"
            description="2つのAIの分析結果をClaude APIで統合。矛盾があれば両方を考慮して最終予測を生成します。"
            ai="Claude"
          />
          <StepCard
            step={3}
            title="可視化"
            description="予測結果を地図・グラフ・カード形式で可視化。確信度で接戦区を識別します。"
            ai="Next.js"
          />
        </div>
      </section>

      {/* Stats */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">処理規模</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div className="border rounded-lg p-4">
            <p className="text-2xl font-bold">289</p>
            <p className="text-sm text-gray-500">小選挙区</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-2xl font-bold">11</p>
            <p className="text-sm text-gray-500">比例ブロック</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-2xl font-bold">3回/日</p>
            <p className="text-sm text-gray-500">更新頻度</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-2xl font-bold">~152</p>
            <p className="text-sm text-gray-500">API呼び出し/更新</p>
          </div>
        </div>
      </section>

      {/* Design Philosophy */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">設計思想</h2>
        <ul className="space-y-3 text-gray-700 dark:text-gray-300">
          <li className="flex gap-2">
            <span className="font-bold text-blue-600">透明性</span>
            <span>使用するプロンプトをすべて公開</span>
          </li>
          <li className="flex gap-2">
            <span className="font-bold text-green-600">多角的分析</span>
            <span>ニュースとSNSの2つの情報源で偏りを低減</span>
          </li>
          <li className="flex gap-2">
            <span className="font-bold text-yellow-600">ハルシネーション対策</span>
            <span>候補者・選挙区データをファクトとして事前に提供</span>
          </li>
          <li className="flex gap-2">
            <span className="font-bold text-red-600">不確実性の可視化</span>
            <span>確信度（高/中/低）で接戦区を明示</span>
          </li>
        </ul>
      </section>

      {/* Prompts */}
      <section>
        <h2 className="text-xl font-bold mb-4">使用プロンプト</h2>
        {prompts ? (
          <div className="space-y-6">
            {Object.entries(prompts).map(([key, value]) => (
              <div key={key} className="border rounded-lg overflow-hidden">
                <div className="bg-gray-50 dark:bg-gray-800 px-4 py-3">
                  <h3 className="font-bold">{value.name}</h3>
                  <p className="text-sm text-gray-500">{value.description}</p>
                </div>
                <pre className="p-4 text-xs overflow-x-auto bg-gray-900 text-gray-100 max-h-96">
                  {value.template}
                </pre>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500">
            プロンプトを表示するにはバックエンドAPIに接続してください
          </p>
        )}
      </section>
    </div>
  );
}

function StepCard({
  step,
  title,
  description,
  ai,
}: {
  step: number;
  title: string;
  description: string;
  ai: string;
}) {
  return (
    <div className="border rounded-lg p-5 relative">
      <div className="absolute -top-3 -left-3 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
        {step}
      </div>
      <h3 className="font-bold mt-2 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
      <p className="text-xs text-blue-600 mt-2 font-semibold">{ai}</p>
    </div>
  );
}
