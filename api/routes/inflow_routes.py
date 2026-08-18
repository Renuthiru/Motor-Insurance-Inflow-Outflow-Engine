# ============================================================
# routes/inflow_routes.py
# ============================================================
# Purpose: API route for POST /calculate-inflow.
#
# EFFECTIVE-DATE FLOW:
#   req.requested_date → standardize_raw_input() [date-agnostic] →
#   InflowCalculator.calculate_rate() → RuleService.perform_rule_lookup()
#   [date resolution happens here, version-locked for all queries]
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
    """
    End-to-end inflow rate calculation.

    Flow:
      1. Standardize raw business input (product, state, etc.)
      2. Resolve Rule Master effective date for req.requested_date
      3. Fetch matching inflow rules (version-locked)
      4. Evaluate vehicle conditions (CC, make, CPA, GVW, age)
      5. Return matched rates per insurer

    Both requested_date and effective_date_used are returned in
    the response for full auditability.
    """
    # 1. Standardize raw user/business input
    # Reuse the RawInflowLookupRequest schema for standardization logic
    from schemas.rule_schema import RawInflowLookupRequest
    raw_lookup = RawInflowLookupRequest(
        requested_date=req.requested_date,
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
            requested_date=req.requested_date,
            effective_date_used=None,
            standardized_input=None,
            results=[],
            error=err
        )

    # 2. Perform lookup and calculate applicable rates based on vehicle inputs
    matched, results, calc_err, effective_date_used = InflowCalculator.calculate_rate(
        db, req, std_info
    )

    return InflowCalculationResponse(
        matched=matched,
        requested_date=req.requested_date,
        effective_date_used=effective_date_used,
        standardized_input=std_info.model_dump() if std_info else None,
        results=results,
        error=calc_err
    )
