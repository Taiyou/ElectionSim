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
