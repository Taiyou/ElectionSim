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
import type { VotingDecisionFactor } from "@/types";

interface VotingFactorsChartProps {
  factors: VotingDecisionFactor[];
}

const FACTOR_COLORS: Record<string, string> = {
  party_loyalty: "#ef4444",
  policy_alignment: "#3b82f6",
  candidate_appeal: "#22c55e",
  media_influence: "#f59e0b",
  local_connection: "#8b5cf6",
  strategic_voting: "#06b6d4",
};

const FACTOR_LABELS: Record<string, string> = {
  party_loyalty: "政党忠誠度",
  policy_alignment: "政策一致度",
  candidate_appeal: "候補者魅力",
  media_influence: "メディア影響",
  local_connection: "地域つながり",
  strategic_voting: "戦略的投票",
};

export default function VotingFactorsChart({ factors }: VotingFactorsChartProps) {
  const data = factors.map((f) => ({
    name: FACTOR_LABELS[f.name] || f.name,
    weight: Math.round(f.weight * 100),
    color: FACTOR_COLORS[f.name] || "#999",
    description: f.description,
  }));

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 100, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" unit="%" />
          <YAxis dataKey="name" type="category" width={90} tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value: number) => `${value}%`}
            labelFormatter={(label: string) => {
              const item = data.find((d) => d.name === label);
              return item ? `${label}: ${item.description}` : label;
            }}
          />
          <Bar dataKey="weight" name="ウェイト">
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
