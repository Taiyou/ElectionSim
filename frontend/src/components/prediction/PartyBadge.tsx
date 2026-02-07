import { PARTY_COLORS, PARTY_NAMES } from "@/lib/constants";

interface PartyBadgeProps {
  partyId: string;
}

export default function PartyBadge({ partyId }: PartyBadgeProps) {
  const color = PARTY_COLORS[partyId] || "#9E9E9E";
  const name = PARTY_NAMES[partyId] || partyId;

  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold text-white"
      style={{ backgroundColor: color }}
    >
      {name}
    </span>
  );
}
