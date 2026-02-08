"use client";

import type { ComparisonReport } from "@/types";

interface AccuracyScorecardProps {
  report: ComparisonReport;
}

function MetricCard({
  label,
  value,
  format,
  good,
}: {
  label: string;
  value: number | boolean | null;
  format: "percent" | "number" | "boolean" | "correlation";
  good?: boolean;
}) {
  if (value === null || value === undefined) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-xs text-gray-500 mb-1">{label}</div>
        <div className="text-lg font-semibold text-gray-400">N/A</div>
      </div>
    );
  }

  let display: string;
  if (format === "percent") {
    display = `${((value as number) * 100).toFixed(1)}%`;
  } else if (format === "number") {
    display = (value as number).toFixed(1);
  } else if (format === "correlation") {
    display = (value as number).toFixed(3);
  } else {
    display = value ? "YES" : "NO";
  }

  const colorClass =
    good === undefined
      ? "text-gray-900"
      : good
        ? "text-green-600"
        : "text-red-600";

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${colorClass}`}>{display}</div>
    </div>
  );
}

export default function AccuracyScorecard({ report }: AccuracyScorecardProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <MetricCard
        label="当選政党一致率"
        value={report.winner_match_rate}
        format="percent"
        good={report.winner_match_rate >= 0.6}
      />
      <MetricCard
        label="議席数 MAE"
        value={report.seat_mae}
        format="number"
        good={report.seat_mae <= 2}
      />
      <MetricCard
        label="投票率相関"
        value={report.turnout_correlation}
        format="correlation"
        good={
          report.turnout_correlation !== null
            ? report.turnout_correlation >= 0.5
            : undefined
        }
      />
      <MetricCard
        label="接戦区精度"
        value={report.battleground_accuracy}
        format="percent"
        good={
          report.battleground_accuracy !== null
            ? report.battleground_accuracy >= 0.5
            : undefined
        }
      />
      <MetricCard
        label="投票率差"
        value={report.turnout_diff}
        format="percent"
        good={
          report.turnout_diff !== null
            ? report.turnout_diff <= 0.05
            : undefined
        }
      />
    </div>
  );
}
