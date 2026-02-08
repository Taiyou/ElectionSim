"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { AbstentionReasonEntry } from "@/types";

interface AbstentionReasonsChartProps {
  reasons: AbstentionReasonEntry[];
}

const COLORS = [
  "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#ec4899",
  "#06b6d4", "#22c55e", "#f97316", "#14b8a6", "#a855f7",
];

export default function AbstentionReasonsChart({
  reasons,
}: AbstentionReasonsChartProps) {
  const data = reasons.map((r) => ({
    name: r.reason,
    value: r.count,
  }));

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={100}
            dataKey="value"
            nameKey="name"
            label={({ name, percent }) =>
              `${name} (${(percent * 100).toFixed(0)}%)`
            }
            labelLine={{ strokeWidth: 1 }}
          >
            {data.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value: number) => [`${value}人`, "棄権者数"]} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
