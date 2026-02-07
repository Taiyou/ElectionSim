"use client";

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
} from "recharts";
import type { NewsDailyCoverage } from "@/types";

interface NewsDailyChartProps {
  dailyCoverage: NewsDailyCoverage[];
}

export default function NewsDailyChart({ dailyCoverage }: NewsDailyChartProps) {
  const data = dailyCoverage.map((d) => ({
    date: d.date.slice(5),
    記事数: d.article_count,
    PV: d.total_page_views,
    論調: d.avg_tone,
    トップイシュー: d.top_issue,
  }));

  return (
    <div className="space-y-8">
      {/* Article count & PV */}
      <div className="w-full h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={11} />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip />
            <Legend />
            <ReferenceLine
              x="01-27"
              yAxisId="left"
              stroke="#ef4444"
              strokeDasharray="3 3"
              label={{ value: "公示日", position: "top", fontSize: 11 }}
            />
            <Bar yAxisId="left" dataKey="記事数" fill="#6366f1" />
            <Line yAxisId="right" dataKey="PV" stroke="#f59e0b" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Tone trend */}
      <div className="w-full h-56">
        <h3 className="text-sm font-semibold text-gray-500 mb-2">報道論調推移</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={11} />
            <YAxis domain={[-1, 1]} />
            <Tooltip />
            <ReferenceLine y={0} stroke="#999" strokeDasharray="3 3" />
            <ReferenceLine
              x="01-27"
              stroke="#ef4444"
              strokeDasharray="3 3"
              label={{ value: "公示日", position: "top", fontSize: 11 }}
            />
            <Line dataKey="論調" stroke="#6366f1" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
