export interface Party {
  id: string;
  name_ja: string;
  name_short: string;
  name_en: string;
  color: string;
  leader: string;
  coalition_group: string | null;
}

export interface Candidate {
  id: number;
  name: string;
  name_kana: string;
  party_id: string;
  age: number | null;
  is_incumbent: boolean;
  previous_wins: number;
  biography: string | null;
  dual_candidacy: boolean;
}

export interface District {
  id: string;
  prefecture: string;
  prefecture_code: number;
  district_number: number;
  name: string;
  area_description: string;
  registered_voters: number | null;
  candidates?: Candidate[];
}

export interface Prediction {
  id: number;
  district_id: string;
  predicted_winner_party_id: string;
  confidence: "high" | "medium" | "low";
  confidence_score: number;
  analysis_summary: string;
  news_summary: string;
  sns_summary: string;
  key_factors: string;
  candidate_rankings: string;
  updated_at: string;
  prediction_batch_id: string;
}

export interface PartySeatCount {
  party_id: string;
  name_short: string;
  color: string;
  district_seats: number;
  proportional_seats: number;
  total_seats: number;
}

export interface PartyCandidateCount {
  party_id: string;
  name_short: string;
  color: string;
  count: number;
}

export interface CandidateStats {
  total_candidates: number;
  total_districts: number;
  incumbent_count: number;
  dual_candidacy_count: number;
  party_breakdown: PartyCandidateCount[];
}

export interface PredictionSummary {
  batch_id: string;
  updated_at: string | null;
  total_seats: number;
  majority_line: number;
  party_seats: PartySeatCount[];
  battleground_count: number;
  confidence_distribution: Record<string, number>;
  candidate_stats: CandidateStats | null;
}

export interface PredictionHistory {
  district_id: string;
  predicted_winner_party_id: string;
  confidence: string;
  confidence_score: number;
  prediction_batch_id: string;
  created_at: string;
}

export interface ProportionalBlock {
  id: string;
  name: string;
  total_seats: number;
  prefectures: string;
}

export interface ProportionalPrediction {
  block_id: string;
  party_id: string;
  predicted_seats: number;
  vote_share_estimate: number;
  analysis_summary: string;
  prediction_batch_id: string;
}

export interface BlockWithPredictions {
  block: ProportionalBlock;
  predictions: ProportionalPrediction[];
}
