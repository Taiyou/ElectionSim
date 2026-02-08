"use client";

import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import type { DistrictComparison } from "@/types";

interface DistrictComparisonTableProps {
  comparisons: DistrictComparison[];
}

function PartyBadge({ party }: { party: string }) {
  const color = PARTY_COLORS[party] || "#999";
  const name = PARTY_NAMES[party] || party;
  return (
    <span
      className="inline-block px-2 py-0.5 rounded text-xs font-medium text-white"
      style={{ backgroundColor: color }}
    >
      {name}
    </span>
  );
}

export default function DistrictComparisonTable({
  comparisons,
}: DistrictComparisonTableProps) {
  const matchCount = comparisons.filter((c) => c.match).length;

  return (
    <div>
      <div className="text-sm text-gray-600 mb-2">
        一致: {matchCount} / {comparisons.length} 選挙区
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="text-left px-3 py-2">選挙区</th>
              <th className="text-center px-3 py-2">シミュレーション</th>
              <th className="text-center px-3 py-2">実績</th>
              <th className="text-center px-3 py-2">一致</th>
            </tr>
          </thead>
          <tbody>
            {comparisons.map((c) => (
              <tr
                key={c.district_id}
                className={`border-b ${c.match ? "" : "bg-red-50"}`}
              >
                <td className="px-3 py-2 font-medium">{c.district_name}</td>
                <td className="px-3 py-2 text-center">
                  <PartyBadge party={c.party_a} />
                </td>
                <td className="px-3 py-2 text-center">
                  <PartyBadge party={c.party_b} />
                </td>
                <td className="px-3 py-2 text-center text-lg">
                  {c.match ? (
                    <span className="text-green-600">&#10003;</span>
                  ) : (
                    <span className="text-red-600">&#10007;</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
