"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { NewsPolling } from "@/types";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";

interface PollingChartProps {
  polling: NewsPolling[];
}

export default function PollingChart({ polling }: PollingChartProps) {
  // Group polling data by survey_date, then party
  const dateMap = new Map<string, Record<string, number>>();
  const partyIds = new Set<string>();

  for (const p of polling) {
    if (!dateMap.has(p.survey_date)) {
      dateMap.set(p.survey_date, {});
    }
    dateMap.get(p.survey_date)![p.party_id] = p.support_rate;
    partyIds.add(p.party_id);
  }

  const data = Array.from(dateMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, rates]) => ({
      date: date.slice(5),
      ...rates,
    }));

  const parties = Array.from(partyIds);

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" fontSize={11} />
          <YAxis unit="%" />
          <Tooltip
            formatter={(value: number, name: string) => [
              `${value.toFixed(1)}%`,
              PARTY_NAMES[name] || name,
            ]}
          />
          <Legend
            formatter={(value: string) => PARTY_NAMES[value] || value}
          />
          {parties.map((pid) => (
            <Line
              key={pid}
              dataKey={pid}
              stroke={PARTY_COLORS[pid] || "#999"}
              strokeWidth={2}
              dot={{ r: 3 }}
              name={pid}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
