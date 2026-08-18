# ============================================================
# routes/rule_routes.py
# ============================================================
# Purpose: FastAPI endpoints for:
#          - Direct 7-code Rule Lookup    (POST /rule-lookup)
#          - End-to-End Raw Inflow Lookup (POST /inflow-lookup)
#          - Standardize & Lookup alias   (POST /standardize-and-lookup)
#          - Effective date availability  (GET  /rule-master/effective-dates)
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from schemas.rule_schema import (
    RuleLookupRequest,
    RuleLookupResponse,
    RawInflowLookupRequest,
    RawInflowLookupResponse,
    EffectiveDatesResponse,
    InsurerInflowResult
)
from services.rule_service import RuleService

router = APIRouter(tags=["Rule Master & Inflow Lookup"])


# -----------------------------------------------------------
# 1. Effective Date Availability
#    GET /rule-master/effective-dates
#
#    Returns the distinct effective_from dates available in
#    rule_master, ordered ascending. Used by calendar UIs to
#    understand which Rule Master versions are available.
# -----------------------------------------------------------
@router.get("/rule-master/effective-dates", response_model=EffectiveDatesResponse)
def get_effective_dates(db: Session = Depends(get_db)):
    """
    Returns all distinct Rule Master effective dates available in the database.
    The UI can use this to understand which calendar dates have a valid version.
    """
    sql = text("""
        SELECT DISTINCT effective_from
        FROM rule_master
        WHERE effective_from IS NOT NULL
        ORDER BY effective_from ASC
    """)
    rows = db.execute(sql).fetchall()
    dates = [r.effective_from for r in rows]
    return EffectiveDatesResponse(count=len(dates), dates=dates)


# -----------------------------------------------------------
# 2. Direct Standardized Rule Lookup
#    POST /rule-lookup
#    Accepts 7 standardized codes + requested_date directly.
# -----------------------------------------------------------
@router.post("/rule-lookup", response_model=RuleLookupResponse)
def lookup_rule_by_codes(
    req: RuleLookupRequest,
    db: Session = Depends(get_db)
):
    """
    Looks up Rule Master using pre-standardized dimension codes.
    The requested_date is used to resolve MAX(effective_from) <= requested_date.
    Returns matched rules for the resolved effective date only.
    """
    matched, results, error_msg, effective_date_used = RuleService.perform_rule_lookup(
        db, req, req.requested_date
    )

    formatted_results = [
        InsurerInflowResult(insurer=r["insurer"], inflow=r["inflow"])
        for r in results
    ]

    return RuleLookupResponse(
        matched=matched,
        requested_date=req.requested_date,
        effective_date_used=effective_date_used,
        count=len(formatted_results),
        results=formatted_results,
        error=error_msg
    )


# -----------------------------------------------------------
# 3. End-to-End Raw Business Inflow Lookup
#    POST /inflow-lookup  &  POST /standardize-and-lookup
#
#    Accepts human-readable raw values (e.g. "Two Wheeler", "Bike")
#    plus a requested_date.
#
#    Flow:
#      Standardize raw input → Build 7-dimension codes →
#      Resolve effective date → Query Rule Master (version-locked)
# -----------------------------------------------------------
@router.post("/inflow-lookup",          response_model=RawInflowLookupResponse)
@router.post("/standardize-and-lookup", response_model=RawInflowLookupResponse)
def end_to_end_inflow_lookup(
    raw_req: RawInflowLookupRequest,
    db: Session = Depends(get_db)
):
    """
    End-to-end lookup: standardizes raw input, resolves effective date,
    then queries Rule Master with full wildcard fallback logic.
    """
    # Step 1: Standardize raw business input
    std_info, err = RuleService.standardize_raw_input(db, raw_req)
    if err:
        return RawInflowLookupResponse(
            matched=False,
            requested_date=raw_req.requested_date,
            effective_date_used=None,
            count=0,
            standardized_input=None,
            results=[],
            error=err
        )

    # Step 2: Build 7-dimension request object (with the requested_date)
    lookup_req = RuleLookupRequest(
        requested_date=raw_req.requested_date,
        product_code=std_info.product_code,
        subproduct_code=std_info.subproduct_code,
        business_type_code=std_info.business_type_code,
        rule_business_variant=std_info.rule_business_variant,
        subline_code=std_info.subline_code,
        state_code=std_info.state_code,
        location_code=std_info.location_code
    )

    # Step 3: Perform RULE_MASTER lookup (effective date resolved inside)
    matched, results, error_msg, effective_date_used = RuleService.perform_rule_lookup(
        db, lookup_req, raw_req.requested_date
    )

    formatted_results = [
        InsurerInflowResult(insurer=r["insurer"], inflow=r["inflow"])
        for r in results
    ]

    return RawInflowLookupResponse(
        matched=matched,
        requested_date=raw_req.requested_date,
        effective_date_used=effective_date_used,
        count=len(formatted_results),
        standardized_input=std_info,
        results=formatted_results,
        error=error_msg
    )
