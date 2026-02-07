"use client";

import { useState } from "react";

interface PersonaPartyHeatmapProps {
  alignment: Record<string, Record<string, number>>;
  personaNames: Record<string, string>;
  partyOrder: { id: string; name: string; color: string }[];
}

function getHeatColor(score: number): string {
  if (score >= 0.7) return "bg-green-600";
  if (score >= 0.55) return "bg-green-500";
  if (score >= 0.4) return "bg-green-400";
  if (score >= 0.3) return "bg-green-300";
  if (score >= 0.2) return "bg-green-200";
  return "bg-green-100";
}

function getTextColor(score: number): string {
  return score >= 0.4 ? "text-white" : "text-gray-700";
}

export default function PersonaPartyHeatmap({
  alignment,
  personaNames,
  partyOrder,
}: PersonaPartyHeatmapProps) {
  const [hoveredCell, setHoveredCell] = useState<{
    persona: string;
    party: string;
    score: number;
  } | null>(null);

  const personaIds = Object.keys(alignment);

  return (
    <div className="relative">
      {/* Tooltip */}
      {hoveredCell && (
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-xs px-3 py-1.5 rounded shadow-lg z-10 whitespace-nowrap">
          {personaNames[hoveredCell.persona]} × {partyOrder.find((p) => p.id === hoveredCell.party)?.name}
          ：適合度 <span className="font-bold">{(hoveredCell.score * 100).toFixed(0)}%</span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-600 sticky left-0 bg-white z-10 min-w-[140px]">
                ペルソナ類型
              </th>
              {partyOrder.map((party) => (
                <th
                  key={party.id}
                  className="px-2 py-2 text-center font-bold min-w-[60px]"
                  style={{ color: party.color }}
                >
                  {party.name.length > 4 ? party.name.slice(0, 3) : party.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {personaIds.map((personaId) => {
              const partyScores = alignment[personaId];
              // Find the max-scoring party for this persona
              let maxParty = "";
              let maxScore = 0;
              for (const [pid, score] of Object.entries(partyScores)) {
                if (score > maxScore) {
                  maxScore = score;
                  maxParty = pid;
                }
              }

              return (
                <tr key={personaId} className="border-t border-gray-100">
                  <td className="px-3 py-2 font-medium text-gray-700 sticky left-0 bg-white z-10">
                    {personaNames[personaId] || personaId}
                  </td>
                  {partyOrder.map((party) => {
                    const score = partyScores[party.id] ?? 0;
                    const isMax = party.id === maxParty;
                    return (
                      <td
                        key={party.id}
                        className={`px-2 py-2 text-center cursor-default transition-transform ${getHeatColor(score)} ${getTextColor(score)} ${
                          isMax ? "ring-2 ring-amber-400 ring-inset font-bold" : ""
                        }`}
                        onMouseEnter={() =>
                          setHoveredCell({
                            persona: personaId,
                            party: party.id,
                            score,
                          })
                        }
                        onMouseLeave={() => setHoveredCell(null)}
                      >
                        {(score * 100).toFixed(0)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-4 text-xs text-gray-500">
        <span>適合度:</span>
        <div className="flex items-center gap-1">
          <span className="w-5 h-4 bg-green-100 rounded inline-block" />
          <span>低</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-5 h-4 bg-green-300 rounded inline-block" />
          <span>中</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-5 h-4 bg-green-500 rounded inline-block" />
          <span>高</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-5 h-4 bg-green-600 rounded inline-block" />
          <span>極高</span>
        </div>
        <span className="ml-2">
          <span className="inline-block w-4 h-3 ring-2 ring-amber-400 ring-inset rounded mr-1" />
          最適合政党
        </span>
      </div>
    </div>
  );
}
