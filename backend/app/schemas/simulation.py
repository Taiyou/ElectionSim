"""シミュレーション関連のPydanticスキーマ"""

from pydantic import BaseModel


class SimulationRequest(BaseModel):
    seed: int = 42
    personas_per_district: int = 100
    district_ids: list[str] | None = None  # None = 全選挙区


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
    duration_seconds: float
    description: str
    tags: list[str]
    parameters: dict
    results_summary: dict


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
    district_comparisons: list[DistrictComparisonResponse]
