"""シミュレーション関連のPydanticスキーマ"""
from __future__ import annotations

from pydantic import BaseModel


class PoliticalClimate(BaseModel):
    """全国政治状況パラメータ（高市人気・政党支持率等）"""
    cabinet_approval_rate: float = 0.65          # 内閣支持率
    cabinet_disapproval_rate: float = 0.20       # 内閣不支持率
    ldp_support_rate: float = 0.38               # 自民党支持率
    chudo_support_rate: float = 0.12             # 中道改革連合支持率
    ishin_support_rate: float = 0.08             # 維新支持率
    dpfp_support_rate: float = 0.06              # 国民民主支持率
    jcp_support_rate: float = 0.04               # 共産党支持率
    no_party_rate: float = 0.30                  # 支持なし（無党派）
    leader_popularity_boost: float = 0.05        # リーダー人気による底上げ効果
    turnout_boost_from_interest: float = 0.02    # 関心の高まりによる投票率影響
    swing_voter_ldp_lean: float = 0.15           # 無党派層の自民傾斜率


class SimulationRequest(BaseModel):
    seed: int = 42
    personas_per_district: int = 100
    district_ids: list[str] | None = None  # None = 全選挙区
    weather_provider: str = "open-meteo"  # "open-meteo" | "openweathermap" | "static"
    political_climate: PoliticalClimate | None = None  # None = デフォルト値を使用


class DistrictResultResponse(BaseModel):
    district_id: str
    district_name: str
    total_personas: int
    turnout_count: int
    turnout_rate: float
    winner: str
    winner_party: str
    winner_votes: int
    runner_up: str
    runner_up_party: str
    runner_up_votes: int
    margin: int
    smd_votes: dict[str, int]
    proportional_votes: dict[str, int]
    archetype_breakdown: dict[str, dict]


class PartySeatBreakdown(BaseModel):
    smd: int
    pr: int
    total: int


class SimulationSummaryResponse(BaseModel):
    total_districts: int
    total_personas: int
    national_turnout_rate: float
    smd_seats: dict[str, int]
    proportional_seats: dict[str, int] | None = None
    total_seats: dict[str, PartySeatBreakdown] | None = None
    majority_threshold: int | None = None
    simulation_config: dict


class ValidationCheckResponse(BaseModel):
    name: str
    passed: bool
    detail: str


class ValidationReportResponse(BaseModel):
    checks: list[ValidationCheckResponse]
    warnings: list[str]
    errors: list[str]
    passed: bool


class SimulationRunResponse(BaseModel):
    summary: SimulationSummaryResponse
    districts: list[DistrictResultResponse]
    validation: ValidationReportResponse


# ─── 実験管理・比較スキーマ ───


class ExperimentMetaResponse(BaseModel):
    experiment_id: str
    created_at: str
    status: str
    duration_seconds: float | None = None
    description: str
    tags: list[str]
    parameters: dict
    results_summary: dict
    has_opinions: bool = False


class ExperimentListResponse(BaseModel):
    experiments: list[ExperimentMetaResponse]


class ExperimentDetailResponse(BaseModel):
    metadata: dict
    district_results: list[dict]
    summary: dict


class DistrictComparisonResponse(BaseModel):
    district_id: str
    district_name: str
    party_a: str
    party_b: str
    match: bool


class ComparisonRequest(BaseModel):
    experiment_a: str
    experiment_b: str  # "actual" で実選挙結果と比較


class ComparisonReportResponse(BaseModel):
    experiment_a: str
    experiment_b: str
    common_districts: int
    winner_match_rate: float
    seat_diff: dict[str, dict]
    seat_mae: float
    turnout_correlation: float | None = None
    battleground_accuracy: float | None = None
    turnout_diff: float | None = None
    margin_correlation: float | None = None
    government_prediction_correct: bool | None = None
    district_comparisons: list[DistrictComparisonResponse]


class ActualResultsResponse(BaseModel):
    available: bool
    election_date: str | None = None
    source: str | None = None
    national_turnout_rate: float | None = None
    party_total_seats: dict[str, dict] | None = None
    district_count: int = 0


class BatchComparisonRequest(BaseModel):
    experiment_ids: list[str]


class BatchComparisonResponse(BaseModel):
    comparisons: list[ComparisonReportResponse]


# ─── 意見集計スキーマ ───


class OpinionOverview(BaseModel):
    total_personas: int
    total_voters: int
    total_abstainers: int
    turnout_rate: float
    total_districts: int


class PartyReasonEntry(BaseModel):
    persona_id: str
    smd_reason: str
    proportional_reason: str
    confidence: float
    district_id: str


class SwingFactorEntry(BaseModel):
    factor: str
    count: int


class AbstentionReasonEntry(BaseModel):
    reason: str
    count: int


class DistrictOpinionSummary(BaseModel):
    district_id: str
    total: int
    voters: int
    turnout_rate: float
    party_distribution: dict[str, int]


class OpinionsSummaryResponse(BaseModel):
    experiment_id: str
    overview: OpinionOverview
    party_reasons: dict[str, list[PartyReasonEntry]]
    party_vote_counts: dict[str, int]
    swing_factors: list[SwingFactorEntry]
    party_swing_factors: dict[str, dict[str, int]]
    abstention_reasons: list[AbstentionReasonEntry]
    district_summaries: list[DistrictOpinionSummary]
