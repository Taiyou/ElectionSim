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

export const PREFECTURE_NAMES: Record<number, string> = {
  1: "北海道", 2: "青森県", 3: "岩手県", 4: "宮城県", 5: "秋田県",
  6: "山形県", 7: "福島県", 8: "茨城県", 9: "栃木県", 10: "群馬県",
  11: "埼玉県", 12: "千葉県", 13: "東京都", 14: "神奈川県", 15: "新潟県",
  16: "富山県", 17: "石川県", 18: "福井県", 19: "山梨県", 20: "長野県",
  21: "岐阜県", 22: "静岡県", 23: "愛知県", 24: "三重県", 25: "滋賀県",
  26: "京都府", 27: "大阪府", 28: "兵庫県", 29: "奈良県", 30: "和歌山県",
  31: "鳥取県", 32: "島根県", 33: "岡山県", 34: "広島県", 35: "山口県",
  36: "徳島県", 37: "香川県", 38: "愛媛県", 39: "高知県", 40: "福岡県",
  41: "佐賀県", 42: "長崎県", 43: "熊本県", 44: "大分県", 45: "宮崎県",
  46: "鹿児島県", 47: "沖縄県",
};

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
