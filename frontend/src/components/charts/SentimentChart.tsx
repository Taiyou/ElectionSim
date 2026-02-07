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
import type { YouTubeSentiment } from "@/types";
import { PARTY_NAMES } from "@/lib/constants";

interface SentimentChartProps {
  sentiments: YouTubeSentiment[];
}

export default function SentimentChart({ sentiments }: SentimentChartProps) {
  const data = sentiments.map((s) => ({
    party: PARTY_NAMES[s.party_id] || s.party_id,
    ポジティブ: Math.round(s.positive_ratio * 100),
    ニュートラル: Math.round(s.neutral_ratio * 100),
    ネガティブ: Math.round(s.negative_ratio * 100),
    平均スコア: s.avg_sentiment_score,
    サンプル数: s.sample_size,
  }));

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" domain={[0, 100]} unit="%" />
          <YAxis dataKey="party" type="category" width={50} fontSize={12} />
          <Tooltip
            formatter={(value: number, name: string) => [`${value}%`, name]}
          />
          <Legend />
          <Bar dataKey="ポジティブ" stackId="sentiment" fill="#22c55e" />
          <Bar dataKey="ニュートラル" stackId="sentiment" fill="#9ca3af" />
          <Bar dataKey="ネガティブ" stackId="sentiment" fill="#ef4444" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
