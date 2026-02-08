"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { DistrictOpinionSummary } from "@/types";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";

interface DistrictVoteDistributionProps {
  districts: DistrictOpinionSummary[];
}

export default function DistrictVoteDistribution({
  districts,
}: DistrictVoteDistributionProps) {
  // Collect all parties across all districts
  const allParties = new Set<string>();
  for (const d of districts) {
    for (const party of Object.keys(d.party_distribution)) {
      allParties.add(party);
    }
  }
  const partyList = Array.from(allParties).sort((a, b) => {
    const totalA = districts.reduce(
      (sum, d) => sum + (d.party_distribution[a] || 0),
      0,
    );
    const totalB = districts.reduce(
      (sum, d) => sum + (d.party_distribution[b] || 0),
      0,
    );
    return totalB - totalA;
  });

  const data = districts.map((d) => ({
    district: d.district_id,
    turnout: `${(d.turnout_rate * 100).toFixed(0)}%`,
    ...Object.fromEntries(
      partyList.map((p) => [p, d.party_distribution[p] || 0]),
    ),
  }));

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 20, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="district" tick={{ fontSize: 11 }} />
          <YAxis />
          <Tooltip />
          <Legend />
          {partyList.map((party) => (
            <Bar
              key={party}
              dataKey={party}
              name={PARTY_NAMES[party] || party}
              stackId="votes"
              fill={PARTY_COLORS[party] || "#999"}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
