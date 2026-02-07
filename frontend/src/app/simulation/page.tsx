"use client";

import { useState } from "react";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import { fetchSimulationPilot, fetchSimulationRun } from "@/lib/api-client";
import type {
  SimulationRunResult,
  SimulationDistrictResult,
} from "@/types";

export default function SimulationPage() {
  const [result, setResult] = useState<SimulationRunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"pilot" | "all">("pilot");

  const runSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
      const data =
        mode === "pilot"
          ? await fetchSimulationPilot()
          : await fetchSimulationRun();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container mx-auto px-4 py-8 max-w-7xl">
      <h1 className="text-2xl font-bold mb-2">
        ペルソナ投票シミュレーション
      </h1>
      <p className="text-gray-600 mb-6">
        12+3アーキタイプ x 100ペルソナ/選挙区のハイブリッドシミュレーション
      </p>

      {/* 実行コントロール */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center gap-4">
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as "pilot" | "all")}
            className="border rounded px-3 py-2"
          >
            <option value="pilot">パイロット（10選挙区）</option>
            <option value="all">全選挙区（289）</option>
          </select>
          <button
            onClick={runSimulation}
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "実行中..." : "シミュレーション実行"}
          </button>
        </div>
        {error && (
          <p className="text-red-600 mt-2">エラー: {error}</p>
        )}
      </div>

      {result && (
        <>
          {/* サマリ */}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">全体サマリ</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold">
                  {result.summary.total_districts}
                </div>
                <div className="text-gray-500 text-sm">選挙区</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">
                  {result.summary.total_personas.toLocaleString()}
                </div>
                <div className="text-gray-500 text-sm">ペルソナ数</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">
                  {(result.summary.national_turnout_rate * 100).toFixed(1)}%
                </div>
                <div className="text-gray-500 text-sm">投票率</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">
                  {result.validation.passed ? "PASS" : "WARN"}
                </div>
                <div className="text-gray-500 text-sm">バリデーション</div>
              </div>
            </div>
          </div>

          {/* 議席配分 */}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">小選挙区 議席配分</h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(result.summary.smd_seats)
                .sort(([, a], [, b]) => b - a)
                .map(([party, seats]) => (
                  <div
                    key={party}
                    className="flex items-center gap-2 px-3 py-2 rounded"
                    style={{
                      backgroundColor:
                        (PARTY_COLORS[party] || "#999") + "20",
                      borderLeft: `4px solid ${PARTY_COLORS[party] || "#999"}`,
                    }}
                  >
                    <span className="font-bold">
                      {PARTY_NAMES[party] || party}
                    </span>
                    <span className="text-xl font-bold">{seats}</span>
                  </div>
                ))}
            </div>
          </div>

          {/* バリデーション結果 */}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold mb-4">バリデーション</h2>
            <div className="space-y-2">
              {result.validation.checks.map((check, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span
                    className={`px-2 py-1 rounded text-xs font-bold ${
                      check.passed
                        ? "bg-green-100 text-green-800"
                        : "bg-yellow-100 text-yellow-800"
                    }`}
                  >
                    {check.passed ? "PASS" : "WARN"}
                  </span>
                  <span className="font-medium">{check.name}</span>
                  <span className="text-gray-500 text-sm">
                    {check.detail}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 選挙区別結果 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold mb-4">選挙区別結果</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left">選挙区</th>
                    <th className="px-3 py-2 text-right">投票率</th>
                    <th className="px-3 py-2 text-left">当選</th>
                    <th className="px-3 py-2 text-left">政党</th>
                    <th className="px-3 py-2 text-right">得票</th>
                    <th className="px-3 py-2 text-left">次点</th>
                    <th className="px-3 py-2 text-right">票差</th>
                  </tr>
                </thead>
                <tbody>
                  {result.districts.map((d: SimulationDistrictResult) => (
                    <tr key={d.district_id} className="border-b">
                      <td className="px-3 py-2 font-medium">
                        {d.district_name}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {(d.turnout_rate * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2">{d.winner}</td>
                      <td className="px-3 py-2">
                        <span
                          className="px-2 py-1 rounded text-xs text-white"
                          style={{
                            backgroundColor:
                              PARTY_COLORS[d.winner_party] || "#999",
                          }}
                        >
                          {PARTY_NAMES[d.winner_party] || d.winner_party}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right">
                        {d.winner_votes}
                      </td>
                      <td className="px-3 py-2 text-gray-500">
                        {d.runner_up}
                      </td>
                      <td className="px-3 py-2 text-right">{d.margin}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
