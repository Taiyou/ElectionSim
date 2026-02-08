"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import type { SeatDiff } from "@/types";

interface SeatComparisonChartProps {
  seatDiff: Record<string, SeatDiff>;
  labelA: string;
  labelB: string;
}

export default function SeatComparisonChart({
  seatDiff,
  labelA,
  labelB,
}: SeatComparisonChartProps) {
  const data = Object.entries(seatDiff)
    .sort(([, a], [, b]) => b.a + b.b - (a.a + a.b))
    .map(([party, d]) => ({
      party: PARTY_NAMES[party] || party,
      [labelA]: d.a,
      [labelB]: d.b,
      diff: d.diff,
    }));

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 10, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="party" />
          <YAxis />
          <Tooltip
            formatter={(value: number, name: string) => [
              `${value} 議席`,
              name,
            ]}
          />
          <Legend />
          <Bar dataKey={labelA} fill="#3b82f6" />
          <Bar dataKey={labelB} fill="#f97316" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
