"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from "react-simple-maps";
import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";
import type { PrefectureMapData, DistrictBrief } from "@/types";

const TOPOJSON_URL = "/japan-prefectures.topojson";

interface JapanMapClientProps {
  prefectureData: PrefectureMapData[];
}

export default function JapanMapClient({ prefectureData }: JapanMapClientProps) {
  const [selectedCode, setSelectedCode] = useState<number | null>(null);
  const [tooltip, setTooltip] = useState<{
    content: string;
    x: number;
    y: number;
  } | null>(null);

  // Build lookup map
  const dataMap = new Map<number, PrefectureMapData>();
  for (const pref of prefectureData) {
    dataMap.set(pref.prefecture_code, pref);
  }

  const selectedData = selectedCode ? dataMap.get(selectedCode) ?? null : null;

  // Get unique leading parties for legend
  const legendParties = new Set<string>();
  for (const pref of prefectureData) {
    legendParties.add(pref.leading_party_id);
  }

  const handleMouseEnter = useCallback(
    (geo: { properties: Record<string, unknown> }, evt: React.MouseEvent) => {
      const prefCode = geo.properties.id as number;
      const data = dataMap.get(prefCode);
      if (!data) return;
      const partyName = PARTY_NAMES[data.leading_party_id] || data.leading_party_id;
      const content = `${data.prefecture_name} — ${data.total_districts}区 ${data.total_candidates}名 — 最多: ${partyName}`;
      const svgRect = (evt.target as SVGElement)
        .closest("svg")
        ?.getBoundingClientRect();
      if (svgRect) {
        setTooltip({
          content,
          x: evt.clientX - svgRect.left + 12,
          y: evt.clientY - svgRect.top - 28,
        });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [prefectureData]
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      {/* Map area */}
      <div className="lg:col-span-3">
        <div className="relative bg-white border border-gray-200 rounded-lg overflow-hidden">
          {/* Tooltip */}
          {tooltip && (
            <div
              className="absolute z-20 bg-gray-900 text-white text-xs rounded px-3 py-2 pointer-events-none whitespace-nowrap shadow-lg"
              style={{ left: tooltip.x, top: tooltip.y }}
            >
              {tooltip.content}
            </div>
          )}

          <ComposableMap
            projection="geoMercator"
            projectionConfig={{
              center: [136.5, 36],
              scale: 1800,
            }}
            width={600}
            height={700}
            style={{ width: "100%", height: "auto" }}
          >
            <ZoomableGroup center={[136.5, 36]} zoom={1} minZoom={0.8} maxZoom={4}>
              <Geographies geography={TOPOJSON_URL}>
                {({ geographies }) =>
                  geographies.map((geo) => {
                    const prefCode = geo.properties.id as number;
                    const data = dataMap.get(prefCode);
                    const color = data
                      ? PARTY_COLORS[data.leading_party_id] || "#D1D5DB"
                      : "#D1D5DB";
                    const isSelected = selectedCode === prefCode;

                    return (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        fill={color}
                        stroke={isSelected ? "#111827" : "#FFFFFF"}
                        strokeWidth={isSelected ? 1.5 : 0.5}
                        style={{
                          default: {
                            outline: "none",
                            opacity: isSelected ? 1 : 0.82,
                          },
                          hover: {
                            outline: "none",
                            opacity: 1,
                            cursor: "pointer",
                          },
                          pressed: { outline: "none" },
                        }}
                        onMouseEnter={(evt) => handleMouseEnter(geo, evt)}
                        onMouseLeave={() => setTooltip(null)}
                        onClick={() => setSelectedCode(prefCode)}
                      />
                    );
                  })
                }
              </Geographies>
            </ZoomableGroup>
          </ComposableMap>
        </div>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap gap-3 px-1">
          {Array.from(legendParties)
            .sort()
            .map((pid) => (
              <div key={pid} className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded"
                  style={{ backgroundColor: PARTY_COLORS[pid] || "#9E9E9E" }}
                />
                <span className="text-xs text-gray-600">
                  {PARTY_NAMES[pid] || pid}
                </span>
              </div>
            ))}
        </div>
        <p className="text-[10px] text-gray-400 mt-1 px-1">
          ※ 色は各都道府県で最多の候補者を擁立している政党を示します
        </p>
      </div>

      {/* Detail sidebar */}
      <div className="lg:col-span-2">
        {selectedData ? (
          <PrefectureDetail data={selectedData} />
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
            <div className="text-4xl mb-3">🗾</div>
            <p className="text-gray-400 text-sm">
              都道府県をクリックして
              <br />
              詳細を表示
            </p>
          </div>
        )}

        {/* Summary stats */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">
              {prefectureData.reduce((s, p) => s + p.total_candidates, 0)}
            </div>
            <div className="text-xs text-gray-500 mt-1">総候補者数</div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">
              {prefectureData.reduce((s, p) => s + p.total_districts, 0)}
            </div>
            <div className="text-xs text-gray-500 mt-1">総選挙区数</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Prefecture detail panel ---

function PrefectureDetail({ data }: { data: PrefectureMapData }) {
  const sorted = [...data.party_breakdown].sort((a, b) => b.count - a.count);
  const maxCount = sorted[0]?.count || 1;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <h3 className="text-lg font-bold mb-1">{data.prefecture_name}</h3>
      <p className="text-sm text-gray-500 mb-4">
        {data.total_districts}選挙区 / {data.total_candidates}候補者
      </p>

      {/* Party breakdown bars */}
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
        政党別候補者数
      </h4>
      <div className="space-y-2 mb-5">
        {sorted.map(({ party_id, count }) => (
          <div key={party_id} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{
                backgroundColor: PARTY_COLORS[party_id] || "#9E9E9E",
              }}
            />
            <span className="text-xs w-12 text-gray-600">
              {PARTY_NAMES[party_id] || party_id}
            </span>
            <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
              <div
                className="h-full rounded-full flex items-center justify-end pr-1.5 transition-all duration-300"
                style={{
                  width: `${Math.max((count / maxCount) * 100, 14)}%`,
                  backgroundColor: PARTY_COLORS[party_id] || "#9E9E9E",
                  opacity: 0.85,
                }}
              >
                <span className="text-[10px] font-bold text-white drop-shadow-sm">
                  {count}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* District list with candidates */}
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
        選挙区一覧
      </h4>
      <div className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
        {data.districts.map((d) => (
          <DistrictCard key={d.id} district={d} />
        ))}
      </div>
    </div>
  );
}

// --- District card with candidate list ---

function DistrictCard({ district }: { district: DistrictBrief }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-xs text-gray-700 py-2 px-3 hover:bg-gray-50 transition"
      >
        <span className="font-medium">{district.name}</span>
        <span className="flex items-center gap-1.5 text-gray-400">
          <span>{district.candidate_count}名</span>
          <svg
            className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </span>
      </button>

      {expanded && district.candidates.length > 0 && (
        <div className="border-t border-gray-100 bg-gray-50/50 px-3 py-2 space-y-1.5">
          {district.candidates.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <div
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{
                  backgroundColor: PARTY_COLORS[c.party_id] || "#9E9E9E",
                }}
              />
              <span className="font-medium text-gray-800">{c.name}</span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                style={{
                  backgroundColor: `${PARTY_COLORS[c.party_id] || "#9E9E9E"}18`,
                  color: PARTY_COLORS[c.party_id] || "#9E9E9E",
                }}
              >
                {PARTY_NAMES[c.party_id] || c.party_id}
              </span>
              {c.is_incumbent && (
                <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium">
                  現職
                </span>
              )}
              {c.previous_wins > 0 && (
                <span className="text-[10px] text-gray-400">{c.previous_wins}期</span>
              )}
              {c.age && (
                <span className="text-[10px] text-gray-400 ml-auto">{c.age}歳</span>
              )}
            </div>
          ))}
          <div className="pt-1">
            <Link
              href={`/district/${district.id}`}
              className="text-[10px] text-blue-500 hover:text-blue-700 hover:underline"
            >
              詳細を見る &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
