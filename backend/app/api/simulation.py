"""シミュレーション API ルーター"""

from fastapi import APIRouter

from ..schemas.simulation import (
    SimulationRequest,
    SimulationRunResponse,
    SimulationSummaryResponse,
    DistrictResultResponse,
    ValidationReportResponse,
    ValidationCheckResponse,
)
from ..services.simulation.engine import SimulationEngine
from ..services.simulation.validators import validate_results

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulationRunResponse)
async def run_simulation(request: SimulationRequest):
    """シミュレーションを実行して結果を返す"""

    engine = SimulationEngine(
        seed=request.seed,
        personas_per_district=request.personas_per_district,
    )

    if request.district_ids:
        results = []
        for district_row in engine.districts:
            did = f"{district_row['都道府県コード'].zfill(2)}_{district_row['区番号']}"
            if did in request.district_ids:
                result = engine.run_district(district_row)
                results.append(result)
    else:
        results = engine.run_all()

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
