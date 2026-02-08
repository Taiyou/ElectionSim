"use client";

import { useState, useEffect } from "react";
import {
  fetchActualResults,
  fetchExperimentList,
  fetchBatchComparison,
} from "@/lib/api-client";
import type {
  ActualResults,
  ComparisonReport,
  ExperimentMeta,
} from "@/types";
import AccuracyScorecard from "@/components/charts/AccuracyScorecard";
import SeatComparisonChart from "@/components/charts/SeatComparisonChart";
import DistrictComparisonTable from "@/components/charts/DistrictComparisonTable";
import ExperimentRankingTable from "@/components/charts/ExperimentRankingTable";

export default function ComparisonPage() {
  const [actual, setActual] = useState<ActualResults | null>(null);
  const [experiments, setExperiments] = useState<ExperimentMeta[]>([]);
  const [selectedExps, setSelectedExps] = useState<string[]>([]);
  const [comparisons, setComparisons] = useState<ComparisonReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initLoading, setInitLoading] = useState(true);

  // Load actual results status + experiments on mount
  useEffect(() => {
    Promise.all([fetchActualResults(), fetchExperimentList()])
      .then(([actualRes, expRes]) => {
        setActual(actualRes);
        const sorted = expRes.experiments.sort((a, b) =>
          b.created_at.localeCompare(a.created_at),
        );
        setExperiments(sorted);
      })
      .catch((e) => setError(e.message))
      .finally(() => setInitLoading(false));
  }, []);

  // Toggle experiment selection
  const toggleExp = (expId: string) => {
    setSelectedExps((prev) =>
      prev.includes(expId)
        ? prev.filter((id) => id !== expId)
        : [...prev, expId],
    );
  };

  // Run comparison
  const runComparison = () => {
    if (selectedExps.length === 0) return;
    setLoading(true);
    setError(null);
    fetchBatchComparison(selectedExps)
      .then((res) => setComparisons(res.comparisons))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const experimentMetaMap: Record<string, ExperimentMeta> = {};
  for (const e of experiments) {
    experimentMetaMap[e.experiment_id] = e;
  }

  const activeReport =
    comparisons.length === 1 ? comparisons[0] : null;

  return (
    <main className="container mx-auto px-4 py-8 max-w-7xl">
      <h1 className="text-2xl font-bold mb-2">
        シミュレーション vs 実選挙結果
      </h1>
      <p className="text-gray-600 mb-6">
        各実験の予測精度を実際の選挙結果と比較・ランキング
      </p>

      {/* Actual results status banner */}
      <div
        className={`rounded-lg p-4 mb-6 ${actual?.available ? "bg-green-50 border border-green-200" : "bg-yellow-50 border border-yellow-200"}`}
      >
        {initLoading ? (
          <span className="text-gray-500">読み込み中...</span>
        ) : actual?.available ? (
          <div>
            <span className="font-semibold text-green-800">
              実選挙結果あり
            </span>
            <span className="text-sm text-green-700 ml-3">
              {actual.election_date && `選挙日: ${actual.election_date}`}
              {actual.source && ` / 出典: ${actual.source}`}
              {actual.district_count > 0 &&
                ` / ${actual.district_count} 選挙区`}
              {actual.national_turnout_rate != null &&
                ` / 投票率: ${(actual.national_turnout_rate * 100).toFixed(1)}%`}
            </span>
          </div>
        ) : (
          <div>
            <span className="font-semibold text-yellow-800">
              実選挙結果が未投入です
            </span>
            <p className="text-sm text-yellow-700 mt-1">
              選挙結果が判明したら以下のコマンドで投入してください:
            </p>
            <code className="block mt-2 text-xs bg-yellow-100 px-3 py-2 rounded font-mono">
              python scripts/load_actual_results.py --summary-only --turnout
              0.52 --seats &quot;ldp:120,chudo:80,...&quot;
            </code>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          {error}
        </div>
      )}

      {/* Experiment selector */}
      <section className="bg-white rounded-lg shadow p-4 mb-6">
        <h2 className="text-sm font-medium text-gray-600 mb-3">
          比較する実験を選択（複数可）:
        </h2>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {experiments.map((exp) => (
            <label
              key={exp.experiment_id}
              className="flex items-center gap-3 text-sm cursor-pointer hover:bg-gray-50 rounded px-2 py-1"
            >
              <input
                type="checkbox"
                checked={selectedExps.includes(exp.experiment_id)}
                onChange={() => toggleExp(exp.experiment_id)}
                className="rounded"
              />
              <span className="font-mono text-xs">{exp.experiment_id}</span>
              <span className="text-gray-500 truncate">
                {exp.description || ""}
              </span>
              <span className="text-xs text-gray-400 ml-auto flex-shrink-0">
                {exp.tags.join(", ")}
              </span>
            </label>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={runComparison}
            disabled={
              selectedExps.length === 0 || !actual?.available || loading
            }
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {loading ? "比較中..." : "比較実行"}
          </button>
          {!actual?.available && (
            <span className="text-xs text-yellow-600">
              実選挙結果を投入してから比較してください
            </span>
          )}
          {selectedExps.length === 0 && actual?.available && (
            <span className="text-xs text-gray-500">
              実験を1つ以上選択してください
            </span>
          )}
        </div>
      </section>

      {/* Results */}
      {comparisons.length > 0 && (
        <>
          {/* Notice about district count */}
          {activeReport && activeReport.common_districts < 289 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-sm text-blue-700">
              289選挙区中 {activeReport.common_districts}{" "}
              選挙区での比較です。統計的な解釈に注意してください。
            </div>
          )}

          {/* Multi-experiment ranking */}
          {comparisons.length > 1 && (
            <section className="bg-white rounded-lg shadow p-6 mb-6">
              <h2 className="text-lg font-bold mb-4">
                実験ランキング（精度順）
              </h2>
              <ExperimentRankingTable
                comparisons={comparisons}
                experimentMetas={experimentMetaMap}
              />
            </section>
          )}

          {/* Single experiment detail (or the best one for multi) */}
          {(() => {
            const report =
              activeReport ||
              [...comparisons].sort(
                (a, b) => b.winner_match_rate - a.winner_match_rate,
              )[0];

            return (
              <>
                {comparisons.length > 1 && (
                  <p className="text-sm text-gray-500 mb-3">
                    以下は最高一致率の実験（{report.experiment_a}）の詳細です
                  </p>
                )}

                {/* Accuracy scorecard */}
                <section className="mb-6">
                  <h2 className="text-lg font-bold mb-3">主要精度指標</h2>
                  <AccuracyScorecard report={report} />
                </section>

                {/* Seat comparison chart */}
                <section className="bg-white rounded-lg shadow p-6 mb-6">
                  <h2 className="text-lg font-bold mb-4">政党別議席数比較</h2>
                  <SeatComparisonChart
                    seatDiff={report.seat_diff}
                    labelA="シミュレーション"
                    labelB="実績"
                  />
                  {/* Seat diff table */}
                  <div className="mt-4 overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b bg-gray-50">
                          <th className="text-left px-3 py-2">政党</th>
                          <th className="text-right px-3 py-2">
                            シミュレーション
                          </th>
                          <th className="text-right px-3 py-2">実績</th>
                          <th className="text-right px-3 py-2">差分</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(report.seat_diff)
                          .sort(
                            ([, a], [, b]) => Math.abs(b.diff) - Math.abs(a.diff),
                          )
                          .map(([party, d]) => (
                            <tr key={party} className="border-b">
                              <td className="px-3 py-2 font-medium">
                                {party}
                              </td>
                              <td className="px-3 py-2 text-right">{d.a}</td>
                              <td className="px-3 py-2 text-right">{d.b}</td>
                              <td
                                className={`px-3 py-2 text-right font-semibold ${d.diff > 0 ? "text-blue-600" : d.diff < 0 ? "text-red-600" : ""}`}
                              >
                                {d.diff > 0 ? `+${d.diff}` : d.diff}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {/* District comparison table */}
                <section className="bg-white rounded-lg shadow p-6 mb-6">
                  <h2 className="text-lg font-bold mb-4">選挙区別比較</h2>
                  <DistrictComparisonTable
                    comparisons={report.district_comparisons}
                  />
                </section>
              </>
            );
          })()}
        </>
      )}
    </main>
  );
}
