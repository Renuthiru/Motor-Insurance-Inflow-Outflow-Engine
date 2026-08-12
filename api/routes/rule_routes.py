# ============================================================
# routes/rule_routes.py
# ============================================================
# Purpose: FastAPI endpoints for:
#          - Direct 7-code Rule Lookup (POST /rule-lookup)
#          - End-to-End Raw Inflow Lookup (POST /inflow-lookup & POST /standardize-and-lookup)
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas.rule_schema import (
    RuleLookupRequest,
    RuleLookupResponse,
    RawInflowLookupRequest,
    RawInflowLookupResponse,
    InsurerInflowResult
)
from services.rule_service import RuleService

router = APIRouter(tags=["Rule Master & Inflow Lookup"])


# -----------------------------------------------------------
# 1. Direct Standardized Rule Lookup
#    POST /rule-lookup
#    Accepts 7 standardized codes directly.
# -----------------------------------------------------------
@router.post("/rule-lookup", response_model=RuleLookupResponse)
def lookup_rule_by_codes(
    req: RuleLookupRequest,
    db: Session = Depends(get_db)
):
    matched, results, error_msg = RuleService.perform_rule_lookup(db, req)
    
    formatted_results = [
        InsurerInflowResult(insurer=r["insurer"], inflow=r["inflow"])
        for r in results
    ]

    return RuleLookupResponse(
        matched=matched,
        count=len(formatted_results),
        results=formatted_results,
        error=error_msg
    )


# -----------------------------------------------------------
# 2. End-to-End Raw Business Inflow Lookup
#    POST /inflow-lookup & POST /standardize-and-lookup
#    Accepts human-readable raw values (e.g. "Two Wheeler", "Bike")
#    Standardizes inputs → Validates State-Location → Searches RULE_MASTER
# -----------------------------------------------------------
@router.post("/inflow-lookup", response_model=RawInflowLookupResponse)
@router.post("/standardize-and-lookup", response_model=RawInflowLookupResponse)
def end_to_end_inflow_lookup(
    raw_req: RawInflowLookupRequest,
    db: Session = Depends(get_db)
):
    # Step 1: Standardize raw business input
    std_info, err = RuleService.standardize_raw_input(db, raw_req)
    if err:
        return RawInflowLookupResponse(
            matched=False,
            count=0,
            standardized_input=None,
            results=[],
            error=err
        )

    # Step 2: Build 7-dimension request object
    lookup_req = RuleLookupRequest(
        product_code=std_info.product_code,
        subproduct_code=std_info.subproduct_code,
        business_type_code=std_info.business_type_code,
        rule_business_variant=std_info.rule_business_variant,
        subline_code=std_info.subline_code,
        state_code=std_info.state_code,
        location_code=std_info.location_code
    )

    # Step 3: Perform RULE_MASTER lookup with wildcard fallbacks
    matched, results, error_msg = RuleService.perform_rule_lookup(db, lookup_req)

    formatted_results = [
        InsurerInflowResult(insurer=r["insurer"], inflow=r["inflow"])
        for r in results
    ]

    return RawInflowLookupResponse(
        matched=matched,
        count=len(formatted_results),
        standardized_input=std_info,
        results=formatted_results,
        error=error_msg
    )
