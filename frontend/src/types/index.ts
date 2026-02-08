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

// YouTube types
export interface YouTubeChannel {
  id: number;
  channel_id: string;
  party_id: string | null;
  channel_name: string;
  channel_url: string | null;
  subscriber_count: number;
  video_count: number;
  total_views: number;
  recent_avg_views: number;
  growth_rate: number;
  updated_at: string;
}

export interface YouTubeVideo {
  id: number;
  video_id: string;
  channel_id: string;
  title: string;
  video_url: string | null;
  published_at: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  party_mention: string | null;
  issue_category: string | null;
  sentiment_score: number;
  collected_at: string;
}

export interface YouTubeSentiment {
  id: number;
  party_id: string;
  positive_ratio: number;
  neutral_ratio: number;
  negative_ratio: number;
  avg_sentiment_score: number;
  sample_size: number;
  analysis_date: string;
}

export interface YouTubeDailyStats {
  id: number;
  date: string;
  total_videos: number;
  total_views: number;
  total_likes: number;
  total_comments: number;
  avg_sentiment: number;
}

export interface YouTubeSummary {
  total_videos: number;
  total_views: number;
  total_channels: number;
  avg_sentiment: number;
  channels: YouTubeChannel[];
  sentiments: YouTubeSentiment[];
  daily_stats: YouTubeDailyStats[];
  recent_videos: YouTubeVideo[];
  issue_distribution: Record<string, number>;
  party_video_counts: Record<string, number>;
  last_updated: string | null;
}

// News types
export interface NewsArticle {
  id: number;
  source: string;
  title: string;
  url: string | null;
  published_at: string;
  page_views: number;
  party_mention: string | null;
  tone_score: number;
  credibility_score: number;
  issue_category: string | null;
  collected_at: string;
}

export interface NewsPolling {
  id: number;
  survey_source: string;
  survey_date: string;
  party_id: string;
  support_rate: number;
  sample_size: number;
}

export interface NewsDailyCoverage {
  id: number;
  date: string;
  article_count: number;
  total_page_views: number;
  avg_tone: number;
  top_issue: string | null;
}

export interface NewsSummary {
  total_articles: number;
  total_page_views: number;
  total_sources: number;
  avg_tone: number;
  articles: NewsArticle[];
  daily_coverage: NewsDailyCoverage[];
  polling: NewsPolling[];
  source_breakdown: Record<string, number>;
  party_coverage_counts: Record<string, number>;
}

// Persona types
export interface PersonaArchetype {
  id: string;
  name_ja: string;
  age_range: [number, number];
  turnout_probability: number;
  swing_tendency: string;
  typical_concerns: string[];
}

export interface VotingDecisionFactor {
  name: string;
  weight: number;
  description: string;
}

export interface RegionalIssue {
  issue: string;
  count: number;
  priority_avg: number;
}

export interface PersonaSummary {
  total_prefectures: number;
  total_archetypes: number;
  avg_turnout_probability: number;
  avg_swing_voter_ratio: number;
  archetypes: PersonaArchetype[];
  national_archetype_distribution: Record<string, number>;
  top_regional_issues: RegionalIssue[];
  voting_factors: VotingDecisionFactor[];
}

// Map types
export interface PartyCount {
  party_id: string;
  count: number;
}

export interface CandidateBrief {
  name: string;
  party_id: string;
  is_incumbent: boolean;
  age: number | null;
  previous_wins: number;
}

export interface DistrictBrief {
  id: string;
  name: string;
  district_number: number;
  candidate_count: number;
  candidates: CandidateBrief[];
}

export interface PrefectureMapData {
  prefecture_code: number;
  prefecture_name: string;
  total_districts: number;
  total_candidates: number;
  leading_party_id: string;
  party_breakdown: PartyCount[];
  districts: DistrictBrief[];
}

// Manifesto types
export interface ManifestoPolicy {
  category: string;
  title: string;
  description: string;
  priority: "high" | "medium" | "low";
  target_personas: string[];
}

export interface PartyManifesto {
  party_id: string;
  party_name: string;
  policies: ManifestoPolicy[];
}

export interface IssueCategoryCount {
  category: string;
  category_name: string;
  party_count: number;
  total_policies: number;
}

export interface PersonaBestParty {
  persona_id: string;
  persona_name: string;
  best_party_id: string;
  best_party_name: string;
  score: number;
}

export interface PartyFocus {
  party_id: string;
  party_name: string;
  focus_type: string;
  focus_label: string;
  high_priority_count: number;
  total_policy_count: number;
}

export interface ManifestoOverview {
  most_contested_category: {
    category: string;
    category_name: string;
    party_count: number;
  };
  least_covered_category: {
    category: string;
    category_name: string;
    total_policies: number;
  };
  persona_best_party: PersonaBestParty[];
  party_focus: PartyFocus[];
  spectrum_groups: Record<string, string[]>;
  persona_coverage: {
    most_targeted: {
      persona_id: string;
      persona_name: string;
      party_count: number;
    };
    least_targeted: {
      persona_id: string;
      persona_name: string;
      party_count: number;
    };
  };
}

export interface ManifestoLink {
  party_id: string;
  party_name: string;
  manifesto_url: string;
  description: string;
}

export interface ManifestoSummary {
  total_parties: number;
  total_categories: number;
  total_policies: number;
  parties: PartyManifesto[];
  persona_party_alignment: Record<string, Record<string, number>>;
  persona_names: Record<string, string>;
  issue_category_breakdown: IssueCategoryCount[];
  policy_comparison_matrix: Record<string, Record<string, string>>;
  overview: ManifestoOverview;
  manifesto_links: ManifestoLink[];
}

// Model comparison types
export interface ModelComparisonEntry {
  model_number: number;
  model_name: string;
  description: string;
  data_sources: string;
  predictions: Record<string, number>;
}

export interface ModelComparison {
  models: ModelComparisonEntry[];
  party_ids: string[];
  majority_line: number;
}

// --- シミュレーション関連 ---

export interface SimulationDistrictResult {
  district_id: string;
  district_name: string;
  total_personas: number;
  turnout_count: number;
  turnout_rate: number;
  winner: string;
  winner_party: string;
  winner_votes: number;
  runner_up: string;
  runner_up_party: string;
  runner_up_votes: number;
  margin: number;
  smd_votes: Record<string, number>;
  proportional_votes: Record<string, number>;
  archetype_breakdown: Record<string, ArchetypeVoteData>;
}

export interface ArchetypeVoteData {
  count: number;
  voted: number;
  smd_parties: Record<string, number>;
  proportional_parties: Record<string, number>;
}

export interface SimulationSummary {
  total_districts: number;
  total_personas: number;
  national_turnout_rate: number;
  smd_seats: Record<string, number>;
  simulation_config: Record<string, unknown>;
}

export interface ValidationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface ValidationReport {
  checks: ValidationCheck[];
  warnings: string[];
  errors: string[];
  passed: boolean;
}

export interface SimulationRunResult {
  summary: SimulationSummary;
  districts: SimulationDistrictResult[];
  validation: ValidationReport;
}

// --- 意見集計関連 ---

export interface OpinionOverview {
  total_personas: number;
  total_voters: number;
  total_abstainers: number;
  turnout_rate: number;
  total_districts: number;
}

export interface PartyReasonEntry {
  persona_id: string;
  smd_reason: string;
  proportional_reason: string;
  confidence: number;
  district_id: string;
}

export interface SwingFactorEntry {
  factor: string;
  count: number;
}

export interface AbstentionReasonEntry {
  reason: string;
  count: number;
}

export interface DistrictOpinionSummary {
  district_id: string;
  total: number;
  voters: number;
  turnout_rate: number;
  party_distribution: Record<string, number>;
}

export interface OpinionsSummary {
  experiment_id: string;
  overview: OpinionOverview;
  party_reasons: Record<string, PartyReasonEntry[]>;
  party_vote_counts: Record<string, number>;
  swing_factors: SwingFactorEntry[];
  party_swing_factors: Record<string, Record<string, number>>;
  abstention_reasons: AbstentionReasonEntry[];
  district_summaries: DistrictOpinionSummary[];
}

export interface ExperimentMeta {
  experiment_id: string;
  created_at: string;
  status: string;
  duration_seconds: number | null;
  description: string;
  tags: string[];
  parameters: Record<string, unknown>;
  results_summary: Record<string, unknown>;
  has_opinions: boolean;
}

export interface ExperimentListResponse {
  experiments: ExperimentMeta[];
}

// ─── 実績比較 ───

export interface DistrictComparison {
  district_id: string;
  district_name: string;
  party_a: string;
  party_b: string;
  match: boolean;
}

export interface SeatDiff {
  a: number;
  b: number;
  diff: number;
}

export interface ComparisonReport {
  experiment_a: string;
  experiment_b: string;
  common_districts: number;
  winner_match_rate: number;
  seat_diff: Record<string, SeatDiff>;
  seat_mae: number;
  turnout_correlation: number | null;
  battleground_accuracy: number | null;
  turnout_diff: number | null;
  margin_correlation: number | null;
  government_prediction_correct: boolean | null;
  district_comparisons: DistrictComparison[];
}

export interface ActualResults {
  available: boolean;
  election_date: string | null;
  source: string | null;
  national_turnout_rate: number | null;
  party_total_seats: Record<
    string,
    { district?: number; proportional?: number; total: number }
  > | null;
  district_count: number;
}

export interface BatchComparisonResponse {
  comparisons: ComparisonReport[];
}
