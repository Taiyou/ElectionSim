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
  ReferenceLine,
} from "recharts";
import type { ModelComparison } from "@/types";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";

interface ModelComparisonChartProps {
  data: ModelComparison;
}

export default function ModelComparisonChart({ data }: ModelComparisonChartProps) {
  const chartData = data.models.map((m) => {
    const entry: Record<string, string | number> = {
      name: `M${m.model_number}`,
    };
    for (const pid of data.party_ids) {
      entry[pid] = m.predictions[pid] || 0;
    }
    return entry;
  });

  return (
    <div className="w-full h-96">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip
            formatter={(value: number, name: string) => [
              `${value}議席`,
              PARTY_NAMES[name] || name,
            ]}
          />
          <Legend
            formatter={(value: string) => PARTY_NAMES[value] || value}
          />
          <ReferenceLine
            y={data.majority_line}
            stroke="#ef4444"
            strokeDasharray="3 3"
            label={{ value: `過半数 ${data.majority_line}`, position: "right", fontSize: 11 }}
          />
          {data.party_ids.map((pid) => (
            <Bar
              key={pid}
              dataKey={pid}
              stackId="seats"
              fill={PARTY_COLORS[pid] || "#999"}
              name={pid}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
