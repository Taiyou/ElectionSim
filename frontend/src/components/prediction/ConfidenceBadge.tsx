import { CONFIDENCE_COLORS, CONFIDENCE_LABELS } from "@/lib/constants";

interface ConfidenceBadgeProps {
  confidence: "high" | "medium" | "low";
  score?: number;
}

export default function ConfidenceBadge({ confidence, score }: ConfidenceBadgeProps) {
  const color = CONFIDENCE_COLORS[confidence] || "#9E9E9E";
  const label = CONFIDENCE_LABELS[confidence] || confidence;

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-white"
      style={{ backgroundColor: color }}
    >
      確信度: {label}
      {score !== undefined && (
        <span className="opacity-80">({(score * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
