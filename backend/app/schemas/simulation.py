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


class SimulationSummaryResponse(BaseModel):
    total_districts: int
    total_personas: int
    national_turnout_rate: float
    smd_seats: dict[str, int]
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
