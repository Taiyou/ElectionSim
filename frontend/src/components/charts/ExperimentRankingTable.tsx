"use client";

import type { ComparisonReport, ExperimentMeta } from "@/types";

interface ExperimentRankingTableProps {
  comparisons: ComparisonReport[];
  experimentMetas: Record<string, ExperimentMeta>;
}

export default function ExperimentRankingTable({
  comparisons,
  experimentMetas,
}: ExperimentRankingTableProps) {
  const sorted = [...comparisons].sort(
    (a, b) => b.winner_match_rate - a.winner_match_rate,
  );

  const bestMatch = Math.max(...sorted.map((c) => c.winner_match_rate));
  const bestMae = Math.min(...sorted.map((c) => c.seat_mae));

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="text-left px-3 py-2">#</th>
            <th className="text-left px-3 py-2">実験</th>
            <th className="text-left px-3 py-2">説明</th>
            <th className="text-right px-3 py-2">一致率</th>
            <th className="text-right px-3 py-2">MAE</th>
            <th className="text-right px-3 py-2">投票率相関</th>
            <th className="text-right px-3 py-2">接戦区精度</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c, i) => {
            const meta = experimentMetas[c.experiment_a];
            const isBestMatch = c.winner_match_rate === bestMatch;
            const isBestMae = c.seat_mae === bestMae;
            return (
              <tr key={c.experiment_a} className="border-b">
                <td className="px-3 py-2 font-medium">{i + 1}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {c.experiment_a}
                </td>
                <td className="px-3 py-2 text-gray-600 max-w-xs truncate">
                  {meta?.description || "-"}
                </td>
                <td
                  className={`px-3 py-2 text-right font-semibold ${isBestMatch ? "text-green-600" : ""}`}
                >
                  {(c.winner_match_rate * 100).toFixed(1)}%
                </td>
                <td
                  className={`px-3 py-2 text-right font-semibold ${isBestMae ? "text-green-600" : ""}`}
                >
                  {c.seat_mae.toFixed(1)}
                </td>
                <td className="px-3 py-2 text-right">
                  {c.turnout_correlation !== null
                    ? c.turnout_correlation.toFixed(3)
                    : "N/A"}
                </td>
                <td className="px-3 py-2 text-right">
                  {c.battleground_accuracy !== null
                    ? `${(c.battleground_accuracy * 100).toFixed(1)}%`
                    : "N/A"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
