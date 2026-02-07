import Link from "next/link";
import type { Prediction } from "@/types";
import ConfidenceBadge from "./ConfidenceBadge";
import PartyBadge from "./PartyBadge";

interface DistrictCardProps {
  prediction: Prediction;
  districtName?: string;
}

export default function DistrictCard({ prediction, districtName }: DistrictCardProps) {
  return (
    <Link
      href={`/district/${prediction.district_id}`}
      className="block border rounded-lg p-4 hover:shadow-md transition bg-white dark:bg-gray-800"
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">
          {districtName || prediction.district_id}
        </h3>
        <ConfidenceBadge
          confidence={prediction.confidence}
          score={prediction.confidence_score}
        />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">予測勝者:</span>
        <PartyBadge partyId={prediction.predicted_winner_party_id} />
      </div>
      <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">
        {prediction.analysis_summary}
      </p>
    </Link>
  );
}
