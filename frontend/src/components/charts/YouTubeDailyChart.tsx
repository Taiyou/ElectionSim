"use client";

import {
  AreaChart,
  Area,
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
import type { YouTubeDailyStats } from "@/types";

interface YouTubeDailyChartProps {
  dailyStats: YouTubeDailyStats[];
}

export default function YouTubeDailyChart({ dailyStats }: YouTubeDailyChartProps) {
  const data = dailyStats.map((d) => ({
    date: d.date.slice(5), // MM-DD
    動画数: d.total_videos,
    視聴数: d.total_views,
    いいね: d.total_likes,
    コメント: d.total_comments,
    センチメント: d.avg_sentiment,
  }));

  return (
    <div className="space-y-8">
      {/* Video count & views */}
      <div className="w-full h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
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
            <Bar yAxisId="left" dataKey="動画数" fill="#3b82f6" />
            <Bar yAxisId="right" dataKey="いいね" fill="#10b981" opacity={0.6} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Sentiment trend */}
      <div className="w-full h-56">
        <h3 className="text-sm font-semibold text-gray-500 mb-2">センチメント推移</h3>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
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
            <Area
              dataKey="センチメント"
              stroke="#8b5cf6"
              fill="#8b5cf6"
              fillOpacity={0.2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
