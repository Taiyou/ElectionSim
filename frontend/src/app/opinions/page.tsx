"use client";

import { useState, useEffect } from "react";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import {
  fetchExperimentList,
  fetchExperimentOpinions,
} from "@/lib/api-client";
import type {
  ExperimentMeta,
  OpinionsSummary,
} from "@/types";
import SwingFactorsChart from "@/components/charts/SwingFactorsChart";
import AbstentionReasonsChart from "@/components/charts/AbstentionReasonsChart";
import DistrictVoteDistribution from "@/components/charts/DistrictVoteDistribution";

export default function OpinionsPage() {
  const [experiments, setExperiments] = useState<ExperimentMeta[]>([]);
  const [selectedExp, setSelectedExp] = useState<string>("");
  const [data, setData] = useState<OpinionsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load experiment list on mount (filter to only those with opinions data)
  useEffect(() => {
    fetchExperimentList()
      .then((res) => {
        const withOpinions = res.experiments
          .filter((e) => e.has_opinions)
          .sort((a, b) => b.created_at.localeCompare(a.created_at));
        setExperiments(withOpinions);
        if (withOpinions.length > 0) {
          setSelectedExp(withOpinions[0].experiment_id);
        }
      })
      .catch((e) => setError(e.message));
  }, []);

  // Load opinions when experiment is selected
  useEffect(() => {
    if (!selectedExp) return;
    setLoading(true);
    setError(null);
    fetchExperimentOpinions(selectedExp)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedExp]);

  return (
    <main className="container mx-auto px-4 py-8 max-w-7xl">
      <h1 className="text-2xl font-bold mb-2">
        ペルソナ意見可視化ダッシュボード
      </h1>
      <p className="text-gray-600 mb-6">
        実験で取得したペルソナの投票理由・棄権理由・影響要因を可視化
      </p>

      {/* Experiment Selector */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <label className="text-sm font-medium text-gray-600 mr-3">
          実験を選択:
        </label>
        <select
          value={selectedExp}
          onChange={(e) => setSelectedExp(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          {experiments.map((exp) => (
            <option key={exp.experiment_id} value={exp.experiment_id}>
              {exp.experiment_id} ({exp.description || "説明なし"})
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12 text-gray-500">
          データを読み込み中...
        </div>
      )}

      {data && !loading && (
        <>
          {/* Section 1: Overview */}
          <section className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">概要</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <StatCard
                label="総ペルソナ数"
                value={data.overview.total_personas.toLocaleString()}
              />
              <StatCard
                label="投票者数"
                value={data.overview.total_voters.toLocaleString()}
                color="text-green-600"
              />
              <StatCard
                label="棄権者数"
                value={data.overview.total_abstainers.toLocaleString()}
                color="text-red-600"
              />
              <StatCard
                label="投票率"
                value={`${(data.overview.turnout_rate * 100).toFixed(1)}%`}
              />
              <StatCard
                label="選挙区数"
                value={`${data.overview.total_districts}`}
              />
            </div>
          </section>

          {/* Section 2: Party Vote Counts + Reasons */}
          <section className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">政党別支持と投票理由</h2>

            {/* Party vote bar */}
            <div className="mb-6">
              <div className="flex rounded-lg overflow-hidden h-10">
                {Object.entries(data.party_vote_counts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([party, count]) => {
                    const pct =
                      (count / data.overview.total_voters) * 100;
                    if (pct < 1) return null;
                    return (
                      <div
                        key={party}
                        className="flex items-center justify-center text-white text-xs font-bold"
                        style={{
                          backgroundColor: PARTY_COLORS[party] || "#999",
                          width: `${pct}%`,
                        }}
                        title={`${PARTY_NAMES[party] || party}: ${count}票 (${pct.toFixed(1)}%)`}
                      >
                        {pct > 5
                          ? `${PARTY_NAMES[party] || party} ${pct.toFixed(0)}%`
                          : ""}
                      </div>
                    );
                  })}
              </div>
              <div className="flex flex-wrap gap-3 mt-2">
                {Object.entries(data.party_vote_counts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([party, count]) => (
                    <span
                      key={party}
                      className="text-xs flex items-center gap-1"
                    >
                      <span
                        className="w-3 h-3 rounded-full inline-block"
                        style={{
                          backgroundColor: PARTY_COLORS[party] || "#999",
                        }}
                      />
                      {PARTY_NAMES[party] || party}: {count}票
                    </span>
                  ))}
              </div>
            </div>

            {/* Party reason cards */}
            <div className="space-y-4">
              {Object.entries(data.party_reasons)
                .sort(([a], [b]) => {
                  const countA = data.party_vote_counts[a] || 0;
                  const countB = data.party_vote_counts[b] || 0;
                  return countB - countA;
                })
                .map(([party, reasons]) => (
                  <div
                    key={party}
                    className="border rounded-lg overflow-hidden"
                    style={{
                      borderLeftWidth: "4px",
                      borderLeftColor: PARTY_COLORS[party] || "#999",
                    }}
                  >
                    <div className="px-4 py-3 bg-gray-50 flex items-center gap-2">
                      <span
                        className="px-2 py-1 rounded text-xs text-white font-bold"
                        style={{
                          backgroundColor: PARTY_COLORS[party] || "#999",
                        }}
                      >
                        {PARTY_NAMES[party] || party}
                      </span>
                      <span className="text-sm text-gray-500">
                        {data.party_vote_counts[party] || 0}票 - 代表的な投票理由
                      </span>
                    </div>
                    <div className="p-4 space-y-3">
                      {reasons.map((r, i) => (
                        <div
                          key={i}
                          className="text-sm border-l-2 border-gray-200 pl-3"
                        >
                          <p className="text-gray-700">{r.smd_reason}</p>
                          <p className="text-xs text-gray-400 mt-1">
                            選挙区: {r.district_id} / 確信度:{" "}
                            {(r.confidence * 100).toFixed(0)}%
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </section>

          {/* Section 3: Swing Factors */}
          <section className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">
              投票判断に影響した要因 (swing_factors)
            </h2>
            <SwingFactorsChart factors={data.swing_factors} />
          </section>

          {/* Section 3b: Party x Swing Factor Heatmap */}
          <section className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">
              政党別 x 影響要因マトリクス
            </h2>
            <PartySwingHeatmap
              partySwingFactors={data.party_swing_factors}
              topFactors={data.swing_factors.slice(0, 10)}
            />
          </section>

          {/* Section 4: Abstention Reasons */}
          <section className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">棄権理由の分布</h2>
            <AbstentionReasonsChart reasons={data.abstention_reasons} />
            <div className="mt-4 space-y-2">
              {data.abstention_reasons.map((r) => (
                <div key={r.reason} className="flex items-center gap-3 text-sm">
                  <span className="w-48 truncate">{r.reason}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-red-400 flex items-center justify-end pr-2"
                      style={{
                        width: `${Math.max(
                          (r.count / data.overview.total_abstainers) * 100,
                          5,
                        )}%`,
                      }}
                    >
                      <span className="text-xs font-bold text-white drop-shadow">
                        {r.count}
                      </span>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 w-12 text-right">
                    {((r.count / data.overview.total_abstainers) * 100).toFixed(
                      0,
                    )}
                    %
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* Section 5: District Vote Distribution */}
          <section className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">選挙区別の投票分布</h2>
            <DistrictVoteDistribution districts={data.district_summaries} />
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left">選挙区</th>
                    <th className="px-3 py-2 text-right">ペルソナ数</th>
                    <th className="px-3 py-2 text-right">投票者</th>
                    <th className="px-3 py-2 text-right">投票率</th>
                    <th className="px-3 py-2 text-left">政党分布</th>
                  </tr>
                </thead>
                <tbody>
                  {data.district_summaries.map((d) => (
                    <tr key={d.district_id} className="border-b">
                      <td className="px-3 py-2 font-medium">
                        {d.district_id}
                      </td>
                      <td className="px-3 py-2 text-right">{d.total}</td>
                      <td className="px-3 py-2 text-right">{d.voters}</td>
                      <td className="px-3 py-2 text-right">
                        {(d.turnout_rate * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex gap-1 flex-wrap">
                          {Object.entries(d.party_distribution)
                            .sort(([, a], [, b]) => b - a)
                            .map(([party, count]) => (
                              <span
                                key={party}
                                className="px-1.5 py-0.5 rounded text-xs text-white font-medium"
                                style={{
                                  backgroundColor:
                                    PARTY_COLORS[party] || "#999",
                                }}
                              >
                                {PARTY_NAMES[party] || party} {count}
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
        </>
      )}
    </main>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold ${color || ""}`}>{value}</div>
      <div className="text-gray-500 text-sm">{label}</div>
    </div>
  );
}

function PartySwingHeatmap({
  partySwingFactors,
  topFactors,
}: {
  partySwingFactors: Record<string, Record<string, number>>;
  topFactors: { factor: string; count: number }[];
}) {
  const parties = Object.keys(partySwingFactors).sort((a, b) => {
    const totalA = Object.values(partySwingFactors[a]).reduce(
      (s, v) => s + v,
      0,
    );
    const totalB = Object.values(partySwingFactors[b]).reduce(
      (s, v) => s + v,
      0,
    );
    return totalB - totalA;
  });

  const factors = topFactors.map((f) => f.factor);

  // Find max value for color scaling
  let maxVal = 0;
  for (const party of parties) {
    for (const factor of factors) {
      const val = partySwingFactors[party]?.[factor] || 0;
      if (val > maxVal) maxVal = val;
    }
  }

  const getOpacity = (val: number) => {
    if (maxVal === 0) return 0.1;
    return Math.max(0.1, val / maxVal);
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-xs">
        <thead>
          <tr>
            <th className="px-3 py-2 text-left font-medium text-gray-600 sticky left-0 bg-white z-10 min-w-[80px]">
              政党
            </th>
            {factors.map((f) => (
              <th
                key={f}
                className="px-2 py-2 text-center font-medium text-gray-600 min-w-[70px]"
              >
                {f}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parties.map((party) => (
            <tr key={party} className="border-t border-gray-100">
              <td className="px-3 py-2 font-medium sticky left-0 bg-white z-10">
                <span
                  className="px-2 py-0.5 rounded text-white text-xs"
                  style={{
                    backgroundColor: PARTY_COLORS[party] || "#999",
                  }}
                >
                  {PARTY_NAMES[party] || party}
                </span>
              </td>
              {factors.map((factor) => {
                const val = partySwingFactors[party]?.[factor] || 0;
                return (
                  <td
                    key={factor}
                    className="px-2 py-2 text-center"
                    style={{
                      backgroundColor: `rgba(99, 102, 241, ${getOpacity(val)})`,
                      color: getOpacity(val) > 0.5 ? "white" : "#374151",
                    }}
                  >
                    {val > 0 ? val : "-"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
