import { fetchPersonaSummary } from "@/lib/api-client";
import ArchetypeDistributionChart from "@/components/charts/ArchetypeDistributionChart";
import VotingFactorsChart from "@/components/charts/VotingFactorsChart";

export const revalidate = 1200;

export default async function PersonasPage() {
  let data;

  try {
    data = await fetchPersonaSummary();
  } catch {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-4">ペルソナ分析</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <p className="text-yellow-800">
            ペルソナデータを取得できません。バックエンドAPIを確認してください。
          </p>
        </div>
      </div>
    );
  }

  const archetypeNames: Record<string, string> = {};
  for (const a of data.archetypes) {
    archetypeNames[a.id] = a.name_ja;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <section className="mb-10">
        <h1 className="text-3xl font-bold mb-2">ペルソナ分析</h1>
        <p className="text-gray-500 text-sm">
          47都道府県の有権者ペルソナ構成と投票行動シミュレーション設定
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <StatCard label="ペルソナ類型数" value={`${data.total_archetypes}`} />
          <StatCard label="対象都道府県" value={`${data.total_prefectures}`} />
          <StatCard
            label="平均投票率"
            value={`${(data.avg_turnout_probability * 100).toFixed(1)}%`}
          />
          <StatCard
            label="平均浮動票率"
            value={`${(data.avg_swing_voter_ratio * 100).toFixed(1)}%`}
            highlight
          />
        </div>
      </section>

      {/* Archetype Overview Table */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">ペルソナ類型一覧</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200 rounded-lg text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">類型名</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">年齢層</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">投票確率</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">浮動性</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">主な関心事</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.archetypes.map((archetype) => (
                <tr key={archetype.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{archetype.name_ja}</td>
                  <td className="px-4 py-3 text-center">
                    {archetype.age_range[0]}~{archetype.age_range[1]}歳
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        archetype.turnout_probability >= 0.7
                          ? "bg-green-100 text-green-700"
                          : archetype.turnout_probability >= 0.5
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-red-100 text-red-700"
                      }`}
                    >
                      {(archetype.turnout_probability * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <SwingBadge tendency={archetype.swing_tendency} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {archetype.typical_concerns.map((concern) => (
                        <span
                          key={concern}
                          className="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600"
                        >
                          {concern}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
        {/* National Archetype Distribution */}
        <section>
          <h2 className="text-xl font-bold mb-4">全国平均ペルソナ構成比</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <ArchetypeDistributionChart
              distribution={data.national_archetype_distribution}
              archetypeNames={archetypeNames}
            />
          </div>
        </section>

        {/* Voting Decision Factors */}
        <section>
          <h2 className="text-xl font-bold mb-4">投票決定要因ウェイト</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <VotingFactorsChart factors={data.voting_factors} />
            <div className="mt-4 space-y-2">
              {data.voting_factors.map((f) => (
                <div key={f.name} className="flex items-start gap-2 text-xs text-gray-500">
                  <span className="font-medium w-20 flex-shrink-0">
                    {(f.weight * 100).toFixed(0)}%
                  </span>
                  <span>{f.description}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* Top Regional Issues */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">全国主要地域課題（出現頻度順）</h2>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="space-y-3">
            {data.top_regional_issues.slice(0, 12).map((issue) => {
              const maxCount = data.top_regional_issues[0]?.count || 1;
              return (
                <div key={issue.issue} className="flex items-center gap-3">
                  <span className="text-sm w-48 truncate flex-shrink-0">{issue.issue}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-purple-500 flex items-center justify-end pr-2"
                      style={{
                        width: `${Math.max((issue.count / maxCount) * 100, 8)}%`,
                        opacity: 0.8,
                      }}
                    >
                      <span className="text-xs font-bold text-white drop-shadow">
                        {issue.count}県
                      </span>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 w-20 text-right flex-shrink-0">
                    優先度 {(issue.priority_avg * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Data Sources & Methodology */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">データソース・分析手法</h2>

        {/* Analysis Methodology */}
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 mb-6">
          <h3 className="font-bold text-purple-800 mb-3">分析手法</h3>
          <div className="space-y-3 text-sm text-gray-700">
            <div className="flex items-start gap-3">
              <span className="bg-purple-200 text-purple-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0">1</span>
              <div>
                <p className="font-medium">ペルソナ類型設計（12類型）</p>
                <p className="text-gray-500">投票行動研究・政治学文献に基づき、年齢層・職業・政治関心度・投票確率・浮動性を定義した12の有権者ペルソナ類型を設計</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="bg-purple-200 text-purple-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0">2</span>
              <div>
                <p className="font-medium">都道府県別ペルソナ構成比の算出</p>
                <p className="text-gray-500">国勢調査（年齢・職業・世帯構成）と労働力調査のデータから、47都道府県ごとに12類型の人口構成比率を加重推計</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="bg-purple-200 text-purple-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0">3</span>
              <div>
                <p className="font-medium">投票決定要因モデル（6要因）</p>
                <p className="text-gray-500">政党忠誠度（30%）・政策一致度（25%）・候補者魅力（20%）・メディア影響（10%）・地域つながり（10%）・戦略的投票（5%）の加重モデルで各ペルソナの投票先を決定</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="bg-purple-200 text-purple-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0">4</span>
              <div>
                <p className="font-medium">加重層化抽出シミュレーション</p>
                <p className="text-gray-500">各選挙区の人口構成比に基づきペルソナを加重抽出し、投票率修正係数（天候・選挙競争度・国民的関心度）を適用して擬似投票を実施</p>
              </div>
            </div>
          </div>
        </div>

        {/* Data Sources Table */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <h3 className="font-bold text-gray-700 px-6 py-4 bg-gray-50 border-b border-gray-200">使用データ一覧</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">カテゴリ</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">データ項目</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">出典</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-600">基準年</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3" rowSpan={4}>
                    <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">人口統計</span>
                  </td>
                  <td className="px-4 py-3">総人口・有権者数</td>
                  <td className="px-4 py-3 text-gray-500">国勢調査（令和2年） — 総務省統計局</td>
                  <td className="px-4 py-3 text-center">2020</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">年齢分布（6区分）</td>
                  <td className="px-4 py-3 text-gray-500">国勢調査 年齢別人口 — 総務省統計局</td>
                  <td className="px-4 py-3 text-center">2020</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">世帯構成（5分類）</td>
                  <td className="px-4 py-3 text-gray-500">国勢調査 世帯類型別 — 総務省統計局</td>
                  <td className="px-4 py-3 text-center">2020</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">都市化率（DID人口比率）</td>
                  <td className="px-4 py-3 text-gray-500">国勢調査 人口集中地区 — 総務省統計局</td>
                  <td className="px-4 py-3 text-center">2020</td>
                </tr>

                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3" rowSpan={4}>
                    <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">社会経済</span>
                  </td>
                  <td className="px-4 py-3">産業構造（一次/二次/三次）</td>
                  <td className="px-4 py-3 text-gray-500">経済センサス — 総務省統計局</td>
                  <td className="px-4 py-3 text-center">2021</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">平均年収・失業率</td>
                  <td className="px-4 py-3 text-gray-500">賃金構造基本統計調査・労働力調査 — 厚生労働省・総務省</td>
                  <td className="px-4 py-3 text-center">2023</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">生活費指数</td>
                  <td className="px-4 py-3 text-gray-500">消費者物価地域差指数 — 総務省統計局</td>
                  <td className="px-4 py-3 text-center">2023</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">高齢化依存率</td>
                  <td className="px-4 py-3 text-gray-500">人口推計 — 総務省統計局</td>
                  <td className="px-4 py-3 text-center">2023</td>
                </tr>

                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3" rowSpan={3}>
                    <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium">政治傾向</span>
                  </td>
                  <td className="px-4 py-3">投票率（2021年・2017年衆院選）</td>
                  <td className="px-4 py-3 text-gray-500">衆議院議員総選挙結果 — 総務省選挙部</td>
                  <td className="px-4 py-3 text-center">2017/2021</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">政党支持率・浮動票率</td>
                  <td className="px-4 py-3 text-gray-500">比例代表得票率・世論調査 — 総務省選挙部・各報道機関</td>
                  <td className="px-4 py-3 text-center">2021-2024</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">イデオロギー・政治関心度</td>
                  <td className="px-4 py-3 text-gray-500">各種世論調査・意識調査 — 明るい選挙推進協会・各報道機関</td>
                  <td className="px-4 py-3 text-center">2021-2024</td>
                </tr>

                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3" rowSpan={2}>
                    <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs font-medium">地域課題</span>
                  </td>
                  <td className="px-4 py-3">主要地域課題・優先度</td>
                  <td className="px-4 py-3 text-gray-500">自治体総合計画・知事施政方針 — 各都道府県庁</td>
                  <td className="px-4 py-3 text-center">2023-2024</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">課題別有利政党</td>
                  <td className="px-4 py-3 text-gray-500">政党公約・マニフェスト比較分析 — 各政党</td>
                  <td className="px-4 py-3 text-center">2024</td>
                </tr>

                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">ペルソナ設計</span>
                  </td>
                  <td className="px-4 py-3">12類型定義・投票決定要因ウェイト</td>
                  <td className="px-4 py-3 text-gray-500">投票行動研究・政治学文献 — 明るい選挙推進協会・学術研究</td>
                  <td className="px-4 py-3 text-center">2021-2024</td>
                </tr>

                <tr className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-medium">選挙区情報</span>
                  </td>
                  <td className="px-4 py-3">289小選挙区定義・候補者情報</td>
                  <td className="px-4 py-3 text-gray-500">衆議院小選挙区区割り・選挙公報 — 総務省・各選挙管理委員会</td>
                  <td className="px-4 py-3 text-center">2024</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Notes */}
        <div className="mt-4 bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="font-bold text-gray-600 text-sm mb-2">注意事項</h3>
          <ul className="text-xs text-gray-500 space-y-1 list-disc list-inside">
            <li>人口統計・社会経済データは都道府県単位の値を使用しています。同一都道府県内の選挙区は同じ都道府県データを共有します。</li>
            <li>政党支持率・イデオロギー分布は比例代表得票率と複数の世論調査データから総合的に推計した値です。</li>
            <li>ペルソナ構成比は国勢調査の年齢・職業・世帯構成データから各類型の人口比率を推計したものであり、実際の投票行動を保証するものではありません。</li>
            <li>投票決定要因のウェイトは投票行動研究の知見に基づく設計値であり、実際の選挙結果と異なる場合があります。</li>
            <li>地域課題・有利政党の判定は各自治体の施策と各政党の政策主張に基づく分析であり、客観的な評価を意図するものではありません。</li>
          </ul>
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
          ? "bg-purple-50 border-purple-200"
          : "bg-white border-gray-200"
      }`}
    >
      <p className={`text-2xl font-bold ${highlight ? "text-purple-600" : ""}`}>
        {value}
      </p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}

function SwingBadge({ tendency }: { tendency: string }) {
  const config: Record<string, { label: string; className: string }> = {
    very_low: { label: "極低", className: "bg-blue-100 text-blue-700" },
    low: { label: "低", className: "bg-green-100 text-green-700" },
    moderate: { label: "中", className: "bg-yellow-100 text-yellow-700" },
    moderate_high: { label: "中高", className: "bg-orange-100 text-orange-700" },
    high: { label: "高", className: "bg-red-100 text-red-700" },
    very_high: { label: "極高", className: "bg-red-200 text-red-800" },
  };

  const c = config[tendency] || { label: tendency, className: "bg-gray-100 text-gray-700" };

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${c.className}`}>
      {c.label}
    </span>
  );
}
