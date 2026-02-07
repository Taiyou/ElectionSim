"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface ArchetypeDistributionChartProps {
  distribution: Record<string, number>;
  archetypeNames: Record<string, string>;
}

const COLORS = [
  "#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#a855f7",
  "#6366f1", "#84cc16",
];

export default function ArchetypeDistributionChart({
  distribution,
  archetypeNames,
}: ArchetypeDistributionChartProps) {
  const data = Object.entries(distribution)
    .map(([id, value], i) => ({
      name: archetypeNames[id] || id,
      value: Math.round(value * 1000) / 10,
      fill: COLORS[i % COLORS.length],
    }))
    .sort((a, b) => b.value - a.value);

  return (
    <div className="w-full h-96">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 120, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" unit="%" />
          <YAxis dataKey="name" type="category" width={110} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value: number) => `${value}%`} />
          <Bar dataKey="value" name="構成比">
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
