# ============================================================
# routes/inflow_routes.py
# ============================================================
# Purpose: API route for POST /calculate-inflow.
# ============================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.inflow_schema import InflowCalculationRequest, InflowCalculationResponse
from services.rule_service import RuleService
from services.inflow_calculator import InflowCalculator

router = APIRouter(tags=["Inflow Calculator"])


# -----------------------------------------------------------
# POST /calculate-inflow
# -----------------------------------------------------------
@router.post("/calculate-inflow", response_model=InflowCalculationResponse)
def calculate_inflow_rate(
    req: InflowCalculationRequest,
    db: Session = Depends(get_db)
):
    # 1. Standardize raw user/business input
    # reuse the RawInflowLookupRequest schema for standardization logic
    from schemas.rule_schema import RawInflowLookupRequest
    raw_lookup = RawInflowLookupRequest(
        product=req.product,
        subproduct=req.subproduct,
        business_type=req.business_type,
        subline=req.subline,
        state=req.state,
        location=req.location,
        rule_business_variant=req.rule_business_variant
    )
    
    std_info, err = RuleService.standardize_raw_input(db, raw_lookup)
    if err:
        return InflowCalculationResponse(
            matched=False,
            standardized_input=None,
            results=[],
            error=err
        )

    # 2. Perform lookup and calculate applicable rates based on vehicle inputs
    matched, results, calc_err = InflowCalculator.calculate_rate(db, req, std_info)
    
    return InflowCalculationResponse(
        matched=matched,
        standardized_input=std_info.model_dump() if std_info else None,
        results=results,
        error=calc_err
    )
