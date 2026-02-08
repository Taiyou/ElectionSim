"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { SwingFactorEntry } from "@/types";

interface SwingFactorsChartProps {
  factors: SwingFactorEntry[];
  maxItems?: number;
}

export default function SwingFactorsChart({
  factors,
  maxItems = 15,
}: SwingFactorsChartProps) {
  const data = factors.slice(0, maxItems).map((f) => ({
    name: f.factor,
    count: f.count,
  }));

  return (
    <div className="w-full h-96">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 140, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis
            dataKey="name"
            type="category"
            width={130}
            tick={{ fontSize: 12 }}
          />
          <Tooltip formatter={(value: number) => [`${value}件`, "出現回数"]} />
          <Bar dataKey="count" name="出現回数" fill="#6366f1" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
