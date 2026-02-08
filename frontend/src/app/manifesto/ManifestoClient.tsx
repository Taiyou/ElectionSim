"use client";

import { useState, useMemo } from "react";
import {
  ISSUE_CATEGORY_NAMES,
  ISSUE_CATEGORY_COLORS,
  MANIFESTO_PARTY_COLORS,
  PARTY_COLORS,
  PARTY_NAMES,
  PARTY_FULL_NAMES,
} from "@/lib/constants";
import PersonaPartyHeatmap from "@/components/charts/PersonaPartyHeatmap";
import type { ManifestoSummary, ManifestoLink, BlockWithPredictions } from "@/types";

/* ────────────────────────────────────────────
   Filter Panel Component
   ──────────────────────────────────────────── */

interface Filters {
  block: string;       // proportional block id, "" = all
  categories: Set<string>;
  parties: Set<string>;
  priorities: Set<string>;
  personas: Set<string>;
}

function emptyFilters(): Filters {
  return {
    block: "",
    categories: new Set<string>(),
    parties: new Set<string>(),
    priorities: new Set<string>(),
    personas: new Set<string>(),
  };
}

function isDefaultFilters(f: Filters): boolean {
  return (
    f.block === "" &&
    f.categories.size === 0 &&
    f.parties.size === 0 &&
    f.priorities.size === 0 &&
    f.personas.size === 0
  );
}

function toggleSet<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

/* chip button for filter */
function Chip({
  label,
  active,
  color,
  onClick,
}: {
  label: string;
  active: boolean;
  color?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-all ${
        active
          ? "text-white shadow-sm"
          : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
      }`}
      style={
        active
          ? { backgroundColor: color || "#3b82f6", borderColor: color || "#3b82f6" }
          : undefined
      }
    >
      {label}
    </button>
  );
}

/* ────────────────────────────────────────────
   Main Client Component
   ──────────────────────────────────────────── */

interface ManifestoClientProps {
  data: ManifestoSummary;
  blocks: BlockWithPredictions[];
}

export default function ManifestoClient({ data, blocks }: ManifestoClientProps) {
  const [filters, setFilters] = useState<Filters>(emptyFilters());
  const [filterOpen, setFilterOpen] = useState(true);

  // ── Derived lists for filter options ──
  const allParties = data.parties.map((p) => ({
    id: p.party_id,
    name: p.party_name,
    color: MANIFESTO_PARTY_COLORS[p.party_id] || "#9E9E9E",
  }));
  const allCategories = Object.entries(ISSUE_CATEGORY_NAMES);
  const allPersonas = Object.entries(data.persona_names);
  const priorityOptions: { id: string; label: string; color: string }[] = [
    { id: "high", label: "高", color: "#ef4444" },
    { id: "medium", label: "中", color: "#eab308" },
    { id: "low", label: "低", color: "#6b7280" },
  ];

  // Block info for selected block
  const selectedBlock = useMemo(
    () => (filters.block ? blocks.find((b) => b.block.id === filters.block) : null),
    [filters.block, blocks]
  );

  // ── Apply filters to data ──
  const filteredParties = useMemo(() => {
    let parties = data.parties;
    // filter by party
    if (filters.parties.size > 0) {
      parties = parties.filter((p) => filters.parties.has(p.party_id));
    }
    // filter policies within each party
    return parties.map((party) => {
      let policies = party.policies;
      if (filters.categories.size > 0) {
        policies = policies.filter((p) => filters.categories.has(p.category));
      }
      if (filters.priorities.size > 0) {
        policies = policies.filter((p) => filters.priorities.has(p.priority));
      }
      if (filters.personas.size > 0) {
        policies = policies.filter((p) =>
          p.target_personas.some((pid) => filters.personas.has(pid))
        );
      }
      return { ...party, policies };
    });
  }, [data.parties, filters]);

  // Filtered party order (only parties that still have policies or were explicitly selected)
  const partyOrder = useMemo(() => {
    if (filters.parties.size > 0) {
      return allParties.filter((p) => filters.parties.has(p.id));
    }
    return allParties;
  }, [allParties, filters.parties]);

  // Policy lookup
  const policyLookup = useMemo(() => {
    const lookup: Record<
      string,
      Record<string, { title: string; description: string; priority: string }>
    > = {};
    for (const party of filteredParties) {
      lookup[party.party_id] = {};
      for (const policy of party.policies) {
        lookup[party.party_id][policy.category] = {
          title: policy.title,
          description: policy.description,
          priority: policy.priority,
        };
      }
    }
    return lookup;
  }, [filteredParties]);

  // Filtered issue categories
  const issueCategories = useMemo(() => {
    if (filters.categories.size > 0) {
      return allCategories.filter(([key]) => filters.categories.has(key));
    }
    return allCategories;
  }, [allCategories, filters.categories]);

  // Filtered alignment for heatmap
  const filteredAlignment = useMemo(() => {
    const alignment = data.persona_party_alignment;
    if (filters.personas.size === 0) return alignment;
    const out: Record<string, Record<string, number>> = {};
    for (const pid of Object.keys(alignment)) {
      if (filters.personas.has(pid)) {
        out[pid] = alignment[pid];
      }
    }
    return out;
  }, [data.persona_party_alignment, filters.personas]);

  // Filtered issue breakdown
  const filteredBreakdown = useMemo(() => {
    let breakdown = data.issue_category_breakdown;
    if (filters.categories.size > 0) {
      breakdown = breakdown.filter((b) => filters.categories.has(b.category));
    }
    return breakdown;
  }, [data.issue_category_breakdown, filters.categories]);

  // Stats based on filters
  const stats = useMemo(() => {
    const visibleParties = new Set(filteredParties.map((p) => p.party_id));
    const totalPolicies = filteredParties.reduce(
      (sum, p) => sum + p.policies.length,
      0
    );
    return {
      parties: visibleParties.size,
      categories: new Set(
        filteredParties.flatMap((p) => p.policies.map((pol) => pol.category))
      ).size,
      policies: totalPolicies,
    };
  }, [filteredParties]);

  // Active filter count
  const activeFilterCount =
    (filters.block ? 1 : 0) +
    filters.categories.size +
    filters.parties.size +
    filters.priorities.size +
    filters.personas.size;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <section className="mb-6">
        <h1 className="text-3xl font-bold mb-2">マニフェスト分析</h1>
        <p className="text-gray-500 text-sm">
          主要政党の政策方針を8つの政策カテゴリで分類し、有権者ペルソナとの対応関係を可視化
        </p>
      </section>

      {/* ═══════════════════════════════════════
          Filter Panel
          ═══════════════════════════════════════ */}
      <section className="mb-8">
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
          <button
            type="button"
            onClick={() => setFilterOpen(!filterOpen)}
            className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              <span className="font-bold text-sm text-gray-700">絞り込み条件</span>
              {activeFilterCount > 0 && (
                <span className="bg-blue-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {activeFilterCount}
                </span>
              )}
            </div>
            <svg
              className={`w-4 h-4 text-gray-400 transition-transform ${filterOpen ? "rotate-180" : ""}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {filterOpen && (
            <div className="border-t border-gray-100 px-5 py-4 space-y-5">
              {/* Block filter */}
              {blocks.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-2">
                    比例代表ブロック予測
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    <Chip
                      label="全ブロック"
                      active={filters.block === ""}
                      color="#6366f1"
                      onClick={() => setFilters((f) => ({ ...f, block: "" }))}
                    />
                    {blocks.map(({ block }) => {
                      let prefectures: string[] = [];
                      try { prefectures = JSON.parse(block.prefectures); } catch { /* empty */ }
                      return (
                        <Chip
                          key={block.id}
                          label={`${block.name}(${block.total_seats})`}
                          active={filters.block === block.id}
                          color="#6366f1"
                          onClick={() =>
                            setFilters((f) => ({
                              ...f,
                              block: f.block === block.id ? "" : block.id,
                            }))
                          }
                        />
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Category filter */}
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-2">
                  政策カテゴリ
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {allCategories.map(([key, name]) => (
                    <Chip
                      key={key}
                      label={name}
                      active={filters.categories.has(key)}
                      color={ISSUE_CATEGORY_COLORS[key]}
                      onClick={() =>
                        setFilters((f) => ({
                          ...f,
                          categories: toggleSet(f.categories, key),
                        }))
                      }
                    />
                  ))}
                </div>
              </div>

              {/* Party filter */}
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-2">
                  政党
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {allParties.map((p) => (
                    <Chip
                      key={p.id}
                      label={p.name}
                      active={filters.parties.has(p.id)}
                      color={p.color}
                      onClick={() =>
                        setFilters((f) => ({
                          ...f,
                          parties: toggleSet(f.parties, p.id),
                        }))
                      }
                    />
                  ))}
                </div>
              </div>

              {/* Priority filter */}
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-2">
                  優先度
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {priorityOptions.map((opt) => (
                    <Chip
                      key={opt.id}
                      label={opt.label}
                      active={filters.priorities.has(opt.id)}
                      color={opt.color}
                      onClick={() =>
                        setFilters((f) => ({
                          ...f,
                          priorities: toggleSet(f.priorities, opt.id),
                        }))
                      }
                    />
                  ))}
                </div>
              </div>

              {/* Persona filter */}
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-2">
                  有権者ペルソナ
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {allPersonas.map(([id, name]) => (
                    <Chip
                      key={id}
                      label={name}
                      active={filters.personas.has(id)}
                      color="#8b5cf6"
                      onClick={() =>
                        setFilters((f) => ({
                          ...f,
                          personas: toggleSet(f.personas, id),
                        }))
                      }
                    />
                  ))}
                </div>
              </div>

              {/* Clear / apply bar */}
              <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                <span className="text-xs text-gray-400">
                  {activeFilterCount > 0
                    ? `${activeFilterCount}件の条件が適用中`
                    : "条件なし（全データ表示）"}
                </span>
                {activeFilterCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setFilters(emptyFilters())}
                    className="text-xs text-red-500 hover:text-red-700 font-medium"
                  >
                    すべてクリア
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ═══════════════════════════════════════
          Proportional Block Detail (when selected)
          ═══════════════════════════════════════ */}
      {selectedBlock && (
        <section className="mb-8">
          <h2 className="text-xl font-bold mb-4">
            比例代表ブロック予測：{selectedBlock.block.name}
          </h2>
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <div className="flex justify-between items-start mb-4">
              <div>
                <p className="text-xs text-gray-500">
                  {(() => {
                    try { return JSON.parse(selectedBlock.block.prefectures).join("・"); } catch { return ""; }
                  })()}
                </p>
              </div>
              <span className="bg-indigo-50 text-indigo-700 rounded px-2 py-1 text-sm font-bold">
                定数 {selectedBlock.block.total_seats}
              </span>
            </div>
            {selectedBlock.predictions.length > 0 ? (
              <div className="space-y-2">
                {selectedBlock.predictions.map((p) => (
                  <div key={p.party_id} className="flex items-center gap-2">
                    <span
                      className="inline-block w-3 h-3 rounded-full flex-shrink-0"
                      style={{
                        backgroundColor: PARTY_COLORS[p.party_id] || MANIFESTO_PARTY_COLORS[p.party_id] || "#9E9E9E",
                      }}
                    />
                    <span className="text-sm w-20 flex-shrink-0">
                      {PARTY_NAMES[p.party_id] || p.party_id}
                    </span>
                    <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                      <div
                        className="h-full rounded-full flex items-center justify-end pr-2"
                        style={{
                          width: `${Math.max((p.predicted_seats / selectedBlock.block.total_seats) * 100, 8)}%`,
                          backgroundColor: PARTY_COLORS[p.party_id] || MANIFESTO_PARTY_COLORS[p.party_id] || "#9E9E9E",
                        }}
                      >
                        <span className="text-[10px] font-bold text-white drop-shadow">
                          {p.predicted_seats}議席
                        </span>
                      </div>
                    </div>
                    <span className="text-xs text-gray-400 w-12 text-right flex-shrink-0">
                      {(p.vote_share_estimate * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">予測データなし</p>
            )}
          </div>
        </section>
      )}

      {/* Stats */}
      <section className="mb-10">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatCard label="分析政党数" value={`${stats.parties}政党`} />
          <StatCard label="政策カテゴリ数" value={`${stats.categories}分野`} />
          <StatCard label="総政策数" value={`${stats.policies}政策`} highlight />
        </div>
      </section>

      {/* ═══════════════════════════════════════
          Official Manifesto Links (from CSV data)
          ═══════════════════════════════════════ */}
      {data.manifesto_links && data.manifesto_links.length > 0 && (
        <section className="mb-10">
          <h2 className="text-xl font-bold mb-4">各政党の公式マニフェスト</h2>
          <p className="text-gray-500 text-xs mb-3">
            各政党の公式政策ページへのリンクです。詳細な政策内容は各政党の公式サイトでご確認ください。
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {data.manifesto_links.map((link: ManifestoLink) => {
              const color = MANIFESTO_PARTY_COLORS[link.party_id] || "#9E9E9E";
              return (
                <a
                  key={link.party_id}
                  href={link.manifesto_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg px-4 py-3 hover:shadow-md hover:border-gray-300 transition-all group"
                >
                  <span
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate group-hover:text-blue-600 transition-colors">
                      {link.party_name}
                    </p>
                    <p className="text-[10px] text-gray-400 truncate">
                      {link.description}
                    </p>
                  </div>
                  <svg
                    className="w-4 h-4 text-gray-300 flex-shrink-0 group-hover:text-blue-500 transition-colors"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                </a>
              );
            })}
          </div>
        </section>
      )}

      {/* ═══════════════════════════════════════
          Overview Insights (only when no filter)
          ═══════════════════════════════════════ */}
      {data.overview && isDefaultFilters(filters) && (
        <section className="mb-10">
          <h2 className="text-xl font-bold mb-4">マニフェスト全体像</h2>
          <p className="text-gray-500 text-xs mb-4">
            10政党の政策方針を横断的に分析した結果から読み取れる、日本の政党政治の構造的特徴をまとめています。
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {/* Political Spectrum */}
            <div className="bg-white border border-gray-200 rounded-lg p-5">
              <h3 className="font-bold text-sm text-gray-700 mb-3">
                政党の政策志向分類
              </h3>
              <p className="text-xs text-gray-500 mb-3">
                各政党が高優先度に掲げる政策分野の傾向から、政策志向を分類しています。
              </p>
              <div className="space-y-3">
                {data.overview.party_focus.map((pf) => {
                  const color = MANIFESTO_PARTY_COLORS[pf.party_id] || "#9E9E9E";
                  const focusConfig: Record<string, { bg: string; text: string }> = {
                    progressive: { bg: "bg-blue-50", text: "text-blue-700" },
                    conservative: { bg: "bg-red-50", text: "text-red-700" },
                    economic: { bg: "bg-amber-50", text: "text-amber-700" },
                    balanced: { bg: "bg-gray-50", text: "text-gray-700" },
                  };
                  const fc = focusConfig[pf.focus_type] || focusConfig.balanced;
                  return (
                    <div key={pf.party_id} className="flex items-center gap-2">
                      <span className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                      <span className="text-sm font-medium w-24 flex-shrink-0">{pf.party_name}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${fc.bg} ${fc.text}`}>{pf.focus_label}</span>
                      <span className="text-[10px] text-gray-400 ml-auto">高優先度 {pf.high_priority_count}/{pf.total_policy_count}件</span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 pt-3 border-t border-gray-100">
                <h4 className="text-xs font-semibold text-gray-600 mb-2">志向別グループ</h4>
                <div className="space-y-1.5">
                  {data.overview.spectrum_groups.economic && data.overview.spectrum_groups.economic.length > 0 && (
                    <div className="flex items-start gap-2 text-xs">
                      <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded font-medium flex-shrink-0">経済重視</span>
                      <span className="text-gray-600">{data.overview.spectrum_groups.economic.join("、")}</span>
                    </div>
                  )}
                  {data.overview.spectrum_groups.progressive && data.overview.spectrum_groups.progressive.length > 0 && (
                    <div className="flex items-start gap-2 text-xs">
                      <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded font-medium flex-shrink-0">生活重視</span>
                      <span className="text-gray-600">{data.overview.spectrum_groups.progressive.join("、")}</span>
                    </div>
                  )}
                  {data.overview.spectrum_groups.conservative && data.overview.spectrum_groups.conservative.length > 0 && (
                    <div className="flex items-start gap-2 text-xs">
                      <span className="px-1.5 py-0.5 bg-red-50 text-red-700 rounded font-medium flex-shrink-0">安保重視</span>
                      <span className="text-gray-600">{data.overview.spectrum_groups.conservative.join("、")}</span>
                    </div>
                  )}
                  {data.overview.spectrum_groups.balanced && data.overview.spectrum_groups.balanced.length > 0 && (
                    <div className="flex items-start gap-2 text-xs">
                      <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded font-medium flex-shrink-0">バランス型</span>
                      <span className="text-gray-600">{data.overview.spectrum_groups.balanced.join("、")}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Persona-Party Best Match */}
            <div className="bg-white border border-gray-200 rounded-lg p-5">
              <h3 className="font-bold text-sm text-gray-700 mb-3">ペルソナ別 最適合政党</h3>
              <p className="text-xs text-gray-500 mb-3">
                各有権者ペルソナが最も政策的に合致する政党と、そのスコアを一覧表示しています。
              </p>
              <div className="space-y-2">
                {data.overview.persona_best_party.map((item) => {
                  const color = MANIFESTO_PARTY_COLORS[item.best_party_id] || "#9E9E9E";
                  return (
                    <div key={item.persona_id} className="flex items-center gap-2">
                      <span className="text-xs w-32 truncate flex-shrink-0 text-gray-700">{item.persona_name}</span>
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold text-white flex-shrink-0" style={{ backgroundColor: color }}>
                        {item.best_party_name.length > 5 ? item.best_party_name.slice(0, 5) : item.best_party_name}
                      </span>
                      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${item.score * 100}%`, backgroundColor: color, opacity: 0.7 }} />
                      </div>
                      <span className="text-[10px] text-gray-500 w-8 text-right flex-shrink-0">{(item.score * 100).toFixed(0)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Summary narrative */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-5">
            <h3 className="font-bold text-amber-800 mb-3 text-sm">分析から読み取れる全体的傾向</h3>
            <div className="space-y-3 text-sm text-gray-700">
              <div>
                <p className="font-medium text-gray-800">1. 経済政策は全政党の最大公約数</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  「{data.overview.most_contested_category.category_name}」分野は{data.overview.most_contested_category.party_count}党が高優先度に掲げており、最も多くの政党が競合する政策領域です。ただし、成長戦略を重視する与党・中道勢力と、分配・格差是正を重視する野党側で方向性が大きく異なります。
                </p>
              </div>
              <div>
                <p className="font-medium text-gray-800">2. 与野党の軸は「安全保障 vs 社会保障」</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  保守系政党（自民・参政・保守）が安全保障・憲法改正を重視する一方、革新系政党（立憲・共産・れいわ・社民）は社会保障・教育・環境を重点に置いており、政策の力点配分に明確な対立軸が存在します。
                </p>
              </div>
              <div>
                <p className="font-medium text-gray-800">3. 若年層・非正規層は野党に政策的親和性</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  都市部若年勤労者・大学生・非正規雇用労働者は、賃上げ・教育無償化・消費税廃止などを掲げるれいわ新選組や立憲民主党との適合度が高い傾向にあります。一方、これらのペルソナは投票率が低く（30〜35%）、政策的親和性が投票行動に直結しにくい構造が見られます。
                </p>
              </div>
              <div>
                <p className="font-medium text-gray-800">4. 中高年・農村層は与党への安定的支持基盤</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  農村部農業従事者（適合度75%）・中高年会社員・自営業者は自民党との適合度が高く、投票率も60〜75%と高いことから、組織的な支持基盤として選挙結果に大きな影響力を持ちます。
                </p>
              </div>
              <div>
                <p className="font-medium text-gray-800">5. 公明党は「生活者目線」の独自ポジション</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  公明党は子育て支援・防災・社会保障に注力し、郊外子育て世帯や専業主婦層との適合度が突出しています。連立パートナーとして与党の政策バランスを補完する役割が政策構造にも表れています。
                </p>
              </div>
              <div>
                <p className="font-medium text-gray-800">6. 政策の空白地帯：{data.overview.least_covered_category.category_name}</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  「{data.overview.least_covered_category.category_name}」は政策登録数が{data.overview.least_covered_category.total_policies}件と最も少なく、各党のマニフェストにおいて相対的に注力度が低い分野です。有権者の関心度との乖離がないか注視が必要です。
                </p>
              </div>
              <div>
                <p className="font-medium text-gray-800">7. 政策対象の偏り</p>
                <p className="text-xs text-gray-600 mt-0.5">
                  最も多くの政党がターゲットとするペルソナは「{data.overview.persona_coverage.most_targeted.persona_name}」（{data.overview.persona_coverage.most_targeted.party_count}党）、最も少ないのは「{data.overview.persona_coverage.least_targeted.persona_name}」（{data.overview.persona_coverage.least_targeted.party_count}党）です。政策のターゲット層に偏りがあり、一部の有権者層が政策的に見過ごされている可能性があります。
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ═══════════════════════════════════════
          Policy Comparison Matrix
          ═══════════════════════════════════════ */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">政策分野別 政党比較マトリクス</h2>
        <p className="text-gray-500 text-xs mb-3">
          各政策分野における各政党の主要政策を一覧比較。優先度は色で表示されます。
        </p>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200 rounded-lg text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600 sticky left-0 bg-gray-50 z-10 min-w-[130px]">
                  政策分野
                </th>
                {partyOrder.map((party) => (
                  <th key={party.id} className="px-3 py-3 text-center font-bold min-w-[110px]">
                    <span className="inline-block px-2 py-0.5 rounded text-xs text-white" style={{ backgroundColor: party.color }}>
                      {party.name.length > 5 ? party.name.slice(0, 4) : party.name}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {issueCategories.map(([catKey, catName]) => (
                <tr key={catKey} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium sticky left-0 bg-white z-10">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: ISSUE_CATEGORY_COLORS[catKey] }} />
                      {catName}
                    </div>
                  </td>
                  {partyOrder.map((party) => {
                    const policy = policyLookup[party.id]?.[catKey];
                    if (!policy) {
                      return (
                        <td key={party.id} className="px-3 py-3 text-center text-gray-300">—</td>
                      );
                    }
                    return (
                      <td key={party.id} className="px-3 py-3">
                        <div className="flex flex-col gap-1">
                          <span className="font-medium text-xs leading-tight">{policy.title}</span>
                          <PriorityBadge priority={policy.priority} />
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          Persona-Party Alignment Heatmap
          ═══════════════════════════════════════ */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">ペルソナ類型 × 政党 適合度ヒートマップ</h2>
        <p className="text-gray-500 text-xs mb-3">
          {Object.keys(filteredAlignment).length}種類の有権者ペルソナ類型と各政党の政策方針がどの程度適合するかを0〜100のスコアで表示。数値が高いほど、その政党の政策がペルソナの関心事項に合致しています。
        </p>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <PersonaPartyHeatmap
            alignment={filteredAlignment}
            personaNames={data.persona_names}
            partyOrder={partyOrder}
          />
        </div>
      </section>

      {/* ═══════════════════════════════════════
          Issue Category Breakdown
          ═══════════════════════════════════════ */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">政策カテゴリ別分析</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-sm mb-4 text-gray-700">カテゴリ別 政策登録数</h3>
            <div className="space-y-3">
              {[...filteredBreakdown].sort((a, b) => b.total_policies - a.total_policies).map((item) => {
                const maxPolicies = Math.max(...filteredBreakdown.map((i) => i.total_policies)) || 1;
                return (
                  <div key={item.category} className="flex items-center gap-3">
                    <span className="text-sm w-32 truncate flex-shrink-0">{item.category_name}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                      <div
                        className="h-full rounded-full flex items-center justify-end pr-2"
                        style={{
                          width: `${Math.max((item.total_policies / maxPolicies) * 100, 12)}%`,
                          backgroundColor: ISSUE_CATEGORY_COLORS[item.category] || "#6b7280",
                          opacity: 0.8,
                        }}
                      >
                        <span className="text-xs font-bold text-white drop-shadow">{item.total_policies}件</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-sm mb-4 text-gray-700">カテゴリ別 高優先度政党数</h3>
            <div className="space-y-3">
              {[...filteredBreakdown].sort((a, b) => b.party_count - a.party_count).map((item) => {
                const maxCount = Math.max(...filteredBreakdown.map((i) => i.party_count)) || 1;
                return (
                  <div key={item.category} className="flex items-center gap-3">
                    <span className="text-sm w-32 truncate flex-shrink-0">{item.category_name}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                      <div
                        className="h-full rounded-full flex items-center justify-end pr-2"
                        style={{
                          width: `${Math.max((item.party_count / maxCount) * 100, 12)}%`,
                          backgroundColor: ISSUE_CATEGORY_COLORS[item.category] || "#6b7280",
                          opacity: 0.8,
                        }}
                      >
                        <span className="text-xs font-bold text-white drop-shadow">{item.party_count}党</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          Party Detail Cards
          ═══════════════════════════════════════ */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">政党別 政策詳細</h2>
        {filteredParties.filter((p) => p.policies.length > 0).length === 0 ? (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
            <p className="text-gray-500">現在のフィルタ条件に一致する政策がありません。</p>
            <button
              type="button"
              onClick={() => setFilters(emptyFilters())}
              className="mt-3 text-sm text-blue-500 hover:text-blue-700 font-medium"
            >
              フィルタをクリアする
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredParties
              .filter((party) => party.policies.length > 0)
              .map((party) => {
                const color = MANIFESTO_PARTY_COLORS[party.party_id] || "#9E9E9E";
                return (
                  <div key={party.party_id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                    <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: `3px solid ${color}` }}>
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-bold text-white" style={{ backgroundColor: color }}>
                        {party.party_name}
                      </span>
                      <span className="text-xs text-gray-500">{party.policies.length}政策</span>
                      {(() => {
                        const link = data.manifesto_links?.find((l: ManifestoLink) => l.party_id === party.party_id);
                        if (!link) return null;
                        return (
                          <a
                            href={link.manifesto_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-auto flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-700 transition-colors"
                            title={`${link.party_name}の公式マニフェストを見る`}
                          >
                            <span>公式サイト</span>
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        );
                      })()}
                    </div>
                    <div className="p-4 space-y-3">
                      {party.policies.map((policy) => (
                        <div key={policy.category} className="flex items-start gap-2">
                          <span
                            className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                            style={{ backgroundColor: ISSUE_CATEGORY_COLORS[policy.category] || "#6b7280" }}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-400">
                                {ISSUE_CATEGORY_NAMES[policy.category] || policy.category}
                              </span>
                              <PriorityBadge priority={policy.priority} />
                            </div>
                            <p className="text-sm font-medium mt-0.5">{policy.title}</p>
                            <p className="text-xs text-gray-500 mt-0.5">{policy.description}</p>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {policy.target_personas.map((pid) => (
                                <span
                                  key={pid}
                                  className={`px-1.5 py-0.5 rounded text-[10px] ${
                                    filters.personas.has(pid)
                                      ? "bg-purple-100 text-purple-700 font-medium"
                                      : "bg-gray-100 text-gray-500"
                                  }`}
                                >
                                  {data.persona_names[pid] || pid}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </section>

      {/* ═══════════════════════════════════════
          Methodology & Data Sources
          ═══════════════════════════════════════ */}
      <section className="mb-10">
        <h2 className="text-xl font-bold mb-4">分析手法・データソース</h2>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 mb-6">
          <h3 className="font-bold text-amber-800 mb-3">分析手法</h3>
          <div className="space-y-3 text-sm text-gray-700">
            <div className="flex items-start gap-3">
              <span className="bg-amber-200 text-amber-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0">1</span>
              <div>
                <p className="font-medium">政策方針の分類（8カテゴリ）</p>
                <p className="text-gray-500">各政党の公約・政策方針を経済・社会保障・安全保障など8つの政策カテゴリに分類し、優先度（高・中・低）を付与</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="bg-amber-200 text-amber-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0">2</span>
              <div>
                <p className="font-medium">ターゲットペルソナの特定</p>
                <p className="text-gray-500">各政策が主にどのペルソナ類型の関心事項に対応するかを、ペルソナの典型的関心事項（typical_concerns）との照合で判定</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="bg-amber-200 text-amber-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold flex-shrink-0">3</span>
              <div>
                <p className="font-medium">ペルソナ-政党適合度マトリクスの算出</p>
                <p className="text-gray-500">各ペルソナ類型の関心事項と各政党の政策方針全体の適合度を0〜1のスコアで評価し、ヒートマップで可視化</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="font-bold text-gray-600 text-sm mb-2">注意事項</h3>
          <ul className="text-xs text-gray-500 space-y-1 list-disc list-inside">
            <li>本データは各政党の公知の政策方針を一般的に要約したものであり、各政党の公式マニフェスト原文の引用ではありません。</li>
            <li>政策の優先度やペルソナ適合度は分析上の推定値であり、各政党の公式見解を反映するものではありません。</li>
            <li>ペルソナ-政党適合度スコアは、各ペルソナの典型的関心事項と政党の政策方針の一般的な対応関係に基づく参考値です。</li>
            <li>政策内容は選挙時期や社会情勢の変化に伴い更新される可能性があります。</li>
            <li>本分析は特定の政党を推奨するものではなく、有権者の投票行動をシミュレーションするための参考データです。</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

/* ────────────────────────────────────────────
   Sub Components
   ──────────────────────────────────────────── */

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-lg p-4 text-center border ${
        highlight ? "bg-amber-50 border-amber-200" : "bg-white border-gray-200"
      }`}
    >
      <p className={`text-2xl font-bold ${highlight ? "text-amber-600" : ""}`}>{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const config: Record<string, { label: string; className: string }> = {
    high: { label: "高", className: "bg-red-100 text-red-700" },
    medium: { label: "中", className: "bg-yellow-100 text-yellow-700" },
    low: { label: "低", className: "bg-gray-100 text-gray-600" },
  };
  const c = config[priority] || { label: priority, className: "bg-gray-100 text-gray-600" };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${c.className}`}>
      {c.label}
    </span>
  );
}
