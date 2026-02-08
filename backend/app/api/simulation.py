"""シミュレーション API ルーター"""

import asyncio

from fastapi import APIRouter, HTTPException

from ..schemas.simulation import (
    PoliticalClimate,
    SimulationRequest,
    SimulationRunResponse,
    SimulationSummaryResponse,
    DistrictResultResponse,
    ValidationReportResponse,
    ValidationCheckResponse,
    ExperimentMetaResponse,
    ExperimentListResponse,
    ExperimentDetailResponse,
    ComparisonRequest,
    ComparisonReportResponse,
    DistrictComparisonResponse,
    OpinionsSummaryResponse,
    ActualResultsResponse,
    BatchComparisonRequest,
    BatchComparisonResponse,
)
from ..services.simulation.engine import SimulationEngine
from ..services.simulation.validators import validate_results
from ..services.experiment_manager import ExperimentManager
from ..services.experiment_comparison import (
    compare_experiments,
    compare_with_actual,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulationRunResponse)
async def run_simulation(request: SimulationRequest):
    """シミュレーションを実行して結果を返す"""

    political_climate_dict = None
    if request.political_climate is not None:
        political_climate_dict = request.political_climate.model_dump()

    engine = SimulationEngine(
        seed=request.seed,
        personas_per_district=request.personas_per_district,
        weather_provider=request.weather_provider,
        political_climate=political_climate_dict,
    )

    if request.district_ids:
        target_rows = [
            row for row in engine.districts
            if f"{row['都道府県コード'].zfill(2)}_{row['区番号']}" in request.district_ids
        ]
        results = await asyncio.to_thread(
            engine._run_districts_parallel,
            [(i, row) for i, row in enumerate(target_rows)],
        )
    else:
        results = await asyncio.to_thread(engine.run_all)

    # バリデーション
    report = validate_results(results)

    # サマリ
    summary_data = engine._build_summary(results)

    # レスポンス構築
    district_responses = [
        DistrictResultResponse(
            district_id=r.district_id,
            district_name=r.district_name,
            total_personas=r.total_personas,
            turnout_count=r.turnout_count,
            turnout_rate=r.turnout_rate,
            winner=r.winner,
            winner_party=r.winner_party,
            winner_votes=r.winner_votes,
            runner_up=r.runner_up,
            runner_up_party=r.runner_up_party,
            runner_up_votes=r.runner_up_votes,
            margin=r.margin,
            smd_votes=r.smd_votes,
            proportional_votes=r.proportional_votes,
            archetype_breakdown=r.archetype_breakdown,
        )
        for r in results
    ]

    validation_response = ValidationReportResponse(
        checks=[
            ValidationCheckResponse(name=c["name"], passed=c["passed"], detail=c["detail"])
            for c in report.checks
        ],
        warnings=report.warnings,
        errors=report.errors,
        passed=report.passed,
    )

    return SimulationRunResponse(
        summary=SimulationSummaryResponse(**summary_data),
        districts=district_responses,
        validation=validation_response,
    )


@router.post("/pilot", response_model=SimulationRunResponse)
async def run_pilot_simulation(seed: int = 42, personas_per_district: int = 100):
    """パイロットシミュレーション（デフォルト10選挙区）を実行"""
    request = SimulationRequest(
        seed=seed,
        personas_per_district=personas_per_district,
        district_ids=[
            "13_1", "01_11", "27_1", "47_1", "23_1",
            "05_1", "14_1", "26_1", "40_1", "32_1",
        ],
    )
    return await run_simulation(request)


# ─── 実験管理エンドポイント ───


@router.get("/experiments", response_model=ExperimentListResponse)
async def list_experiments():
    """保存済み実験の一覧を取得"""
    manager = ExperimentManager()
    experiments = manager.list_experiments()
    return ExperimentListResponse(
        experiments=[
            ExperimentMetaResponse(
                experiment_id=e["experiment_id"],
                created_at=e.get("created_at", ""),
                status=e.get("status", "completed"),
                duration_seconds=e.get("duration_seconds", 0),
                description=e.get("description", ""),
                tags=e.get("tags", []),
                parameters=e.get("parameters", {}),
                results_summary=e.get("results_summary", {}),
                has_opinions=e.get("has_opinions", False),
            )
            for e in experiments
        ]
    )


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetailResponse)
async def get_experiment(experiment_id: str):
    """指定実験の詳細を取得"""
    manager = ExperimentManager()
    try:
        data = manager.load_experiment(experiment_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ExperimentDetailResponse(**data)


@router.post("/compare", response_model=ComparisonReportResponse)
async def compare_two_experiments(request: ComparisonRequest):
    """2つの実験を比較（experiment_b="actual" で実選挙結果と比較）"""
    try:
        if request.experiment_b == "actual":
            report = compare_with_actual(request.experiment_a)
        else:
            report = compare_experiments(request.experiment_a, request.experiment_b)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return _report_to_response(report)


@router.get(
    "/experiments/{experiment_id}/opinions",
    response_model=OpinionsSummaryResponse,
)
async def get_experiment_opinions(experiment_id: str):
    """指定実験のペルソナ意見集計データを取得"""
    manager = ExperimentManager()
    try:
        data = manager.load_opinions(experiment_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return OpinionsSummaryResponse(**data)


# ─── 実績比較エンドポイント ───


def _report_to_response(report) -> ComparisonReportResponse:
    """ComparisonReport dataclass を Response schema に変換"""
    return ComparisonReportResponse(
        experiment_a=report.experiment_a,
        experiment_b=report.experiment_b,
        common_districts=report.common_districts,
        winner_match_rate=report.winner_match_rate,
        seat_diff=report.seat_diff,
        seat_mae=report.seat_mae,
        turnout_correlation=report.turnout_correlation,
        battleground_accuracy=report.battleground_accuracy,
        turnout_diff=report.turnout_diff,
        margin_correlation=report.margin_correlation,
        government_prediction_correct=report.government_prediction_correct,
        district_comparisons=[
            DistrictComparisonResponse(
                district_id=c.district_id,
                district_name=c.district_name,
                party_a=c.party_a,
                party_b=c.party_b,
                match=c.match,
            )
            for c in report.district_comparisons
        ],
    )


@router.get("/actual-results", response_model=ActualResultsResponse)
async def get_actual_results():
    """実選挙結果の存在確認とデータ取得"""
    manager = ExperimentManager()
    actual = manager.load_actual_results()

    if actual is None:
        return ActualResultsResponse(available=False)

    summary = actual.get("summary", {})
    district_results = actual.get("district_results", [])

    return ActualResultsResponse(
        available=True,
        election_date=summary.get("election_date"),
        source=summary.get("source"),
        national_turnout_rate=summary.get("national_turnout_rate"),
        party_total_seats=summary.get("party_total_seats"),
        district_count=len(district_results),
    )


@router.post("/compare-batch", response_model=BatchComparisonResponse)
async def compare_batch_vs_actual(request: BatchComparisonRequest):
    """複数の実験を一括で実選挙結果と比較"""
    comparisons = []
    for exp_id in request.experiment_ids:
        try:
            report = compare_with_actual(exp_id)
            comparisons.append(_report_to_response(report))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return BatchComparisonResponse(comparisons=comparisons)
