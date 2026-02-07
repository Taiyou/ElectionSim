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
import type { PartySeatCount } from "@/types";

interface SeatDistributionProps {
  partySeats: PartySeatCount[];
  majorityLine: number;
}

export default function SeatDistribution({
  partySeats,
  majorityLine,
}: SeatDistributionProps) {
  const data = partySeats.map((p) => ({
    name: p.name_short,
    小選挙区: p.district_seats,
    比例: p.proportional_seats,
    fill: p.color,
  }));

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis dataKey="name" type="category" width={50} />
          <Tooltip />
          <Legend />
          <ReferenceLine
            x={majorityLine}
            stroke="#ef4444"
            strokeDasharray="3 3"
            label={{ value: `過半数 ${majorityLine}`, position: "top" }}
          />
          <Bar dataKey="小選挙区" stackId="seats" fill="#3b82f6" />
          <Bar dataKey="比例" stackId="seats" fill="#93c5fd" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
