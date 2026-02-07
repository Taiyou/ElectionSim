export const PARTY_COLORS: Record<string, string> = {
  ldp: "#E2342B",
  chudo: "#1E50A2",
  ishin: "#00A95F",
  dpfp: "#FFD700",
  jcp: "#BE0032",
  reiwa: "#ED72A0",
  sansei: "#8BC34A",
  genzei: "#FF9800",
  hoshuto: "#9C27B0",
  shamin: "#00BCD4",
  mirai: "#03A9F4",
  shoha: "#795548",
  independent: "#9E9E9E",
};

export const PARTY_NAMES: Record<string, string> = {
  ldp: "自民",
  chudo: "中道",
  ishin: "維新",
  dpfp: "国民",
  jcp: "共産",
  reiwa: "れいわ",
  sansei: "参政",
  genzei: "減ゆ",
  hoshuto: "保守",
  shamin: "社民",
  mirai: "みらい",
  shoha: "諸派",
  independent: "無所属",
};

export const CONFIDENCE_COLORS: Record<string, string> = {
  high: "#22c55e",
  medium: "#eab308",
  low: "#ef4444",
};

export const CONFIDENCE_LABELS: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
