# ============================================================
# services/inflow_calculator.py
# ============================================================
# Purpose: Core calculation engine that evaluates vehicle and
#          business conditions against parsed inflow expressions.
# ============================================================

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from schemas.rule_schema import RuleLookupRequest
from schemas.inflow_schema import InflowCalculationRequest, CalculatedInsurerResult
from services.rule_service import RuleService
from services.inflow_parser import InflowParser


class InflowCalculator:

    @classmethod
    def calculate_rate(
        cls,
        db: Session,
        req: InflowCalculationRequest,
        std_codes: Any
    ) -> Tuple[bool, List[CalculatedInsurerResult], Optional[str]]:
        """
        Executes Rule Master lookup using standardized codes, then evaluates
        parsed segment conditions against vehicle specs to return matching rates.
        """
        # 1. Perform Rule Lookup (with wildcard fallbacks)
        lookup_req = RuleLookupRequest(
            product_code=std_codes.product_code,
            subproduct_code=std_codes.subproduct_code,
            business_type_code=std_codes.business_type_code,
            rule_business_variant=std_codes.rule_business_variant,
            subline_code=std_codes.subline_code,
            state_code=std_codes.state_code,
            location_code=std_codes.location_code
        )
        
        matched, db_rules, error_msg = RuleService.perform_rule_lookup(db, lookup_req)
        if not matched:
            return False, [], error_msg or "No matching rule found in database"

        results = []

        # 2. Iterate through each matching insurer rule
        for rule in db_rules:
            insurer = rule["insurer"]
            raw_inflow = rule["inflow"]

            # Parse inflow text into structured segments
            segments = InflowParser.parse_expression(raw_inflow)
            
            matched_segment = None
            highest_score = -1

            # Match segments against vehicle parameters
            for seg in segments:
                # Calculate specificity matching score
                score = 0
                is_match = True

                # A. Coverage Filter
                if req.coverage:
                    if seg["coverage"] != "ALL" and seg["coverage"].upper() != req.coverage.upper():
                        is_match = False

                # B. CPA Filter
                if req.cpa is not None and seg["cpa"] is not None:
                    if seg["cpa"] != req.cpa:
                        is_match = False
                    else:
                        score += 3

                # C. Engine CC Filter
                if req.engine_cc is not None:
                    if seg["cc_min"] is not None or seg["cc_max"] is not None:
                        min_cc = seg["cc_min"] or 0
                        max_cc = seg["cc_max"] or 999999
                        if not (min_cc <= req.engine_cc <= max_cc):
                            is_match = False
                        else:
                            score += 5

                # D. GVW Filter
                if req.gvw is not None:
                    if seg["gvw_min"] is not None or seg["gvw_max"] is not None:
                        min_gvw = seg["gvw_min"] or 0
                        max_gvw = seg["gvw_max"] or 9999999
                        if not (min_gvw <= req.gvw <= max_gvw):
                            is_match = False
                        else:
                            score += 5

                # E. Vehicle Make Filter
                if req.vehicle_make and seg["allowed_makes"]:
                    user_make_upper = req.vehicle_make.strip().upper()
                    if not any(make in user_make_upper for make in seg["allowed_makes"]):
                        is_match = False
                    else:
                        score += 10

                # F. Exclude Model Filter
                if req.vehicle_model and seg["exclude_models"]:
                    user_model_upper = req.vehicle_model.strip().upper()
                    if any(exc in user_model_upper for exc in seg["exclude_models"]):
                        is_match = False

                # G. Vehicle Age Filter
                if req.vehicle_age is not None:
                    if seg["age_min"] is not None or seg["age_max"] is not None:
                        min_age = seg["age_min"] or 0
                        max_age = seg["age_max"] or 99
                        if not (min_age <= req.vehicle_age <= max_age):
                            is_match = False
                        else:
                            score += 2

                if is_match and score > highest_score:
                    highest_score = score
                    matched_segment = seg

            if matched_segment:
                # Map conditions dict for client transparency
                conditions_info = {
                    "coverage": matched_segment["coverage"],
                    "cpa": matched_segment["cpa"],
                    "cc_min": matched_segment["cc_min"],
                    "cc_max": matched_segment["cc_max"],
                    "gvw_min": matched_segment["gvw_min"],
                    "gvw_max": matched_segment["gvw_max"],
                    "allowed_makes": matched_segment["allowed_makes"],
                    "exclude_models": matched_segment["exclude_models"],
                    "age_min": matched_segment["age_min"],
                    "age_max": matched_segment["age_max"],
                }
                
                results.append(CalculatedInsurerResult(
                    insurer=insurer,
                    rate=matched_segment["rate"],
                    matched_rule=f"{matched_segment['rate']}%{{{matched_segment['raw']}}}",
                    raw_inflow=raw_inflow,
                    conditions=conditions_info
                ))
            else:
                # If no specific segment conditions matched but there is a default (unconditional) segment
                unconditional_seg = next((s for s in segments if s["coverage"] == "ALL" and s["cpa"] is None and s["cc_max"] is None and not s["allowed_makes"]), None)
                if unconditional_seg:
                    results.append(CalculatedInsurerResult(
                        insurer=insurer,
                        rate=unconditional_seg["rate"],
                        matched_rule=f"{unconditional_seg['rate']}%{{{unconditional_seg['raw']}}}",
                        raw_inflow=raw_inflow,
                        conditions={"unconditional": True}
                    ))

        if not results:
            return False, [], "No segments within rule matched the provided vehicle inputs"

        return True, results, None
