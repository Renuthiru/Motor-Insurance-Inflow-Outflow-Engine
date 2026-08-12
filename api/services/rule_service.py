# ============================================================
# services/rule_service.py
# ============================================================
# Purpose: Core business logic for:
#          1. Standardizing raw input values via Mapping tables.
#          2. Validating State-Location relationships.
#          3. Querying RULE_MASTER with wildcard precedence.
# ============================================================

from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from schemas.rule_schema import (
    RuleLookupRequest,
    RawInflowLookupRequest,
    StandardizedCodesInfo,
    InsurerInflowResult
)


class RuleService:

    @staticmethod
    def execute_rule_query(
        db: Session,
        product_code: Optional[str],
        subproduct_code: Optional[str],
        business_type_code: Optional[str],
        rule_business_variant: Optional[str],
        subline_code: Optional[str],
        state_code: Optional[str],
        location_code: Optional[str]
    ) -> List[Dict[str, str]]:
        """
        Executes parameterized SELECT on rule_master for a given set of dimension codes (supports optional/partial dimensions).
        Returns list of dicts: [{"insurer": ..., "inflow": ...}]
        """
        sql = text("""
            SELECT DISTINCT insurer, inflow
            FROM rule_master
            WHERE (:product_code IS NULL OR product_code = :product_code)
              AND (:subproduct_code IS NULL OR subproduct_code = :subproduct_code)
              AND (:business_type_code IS NULL OR business_type_code = :business_type_code)
              AND (:rule_business_variant IS NULL OR rule_business_variant = :rule_business_variant)
              AND (:subline_code IS NULL OR subline_code = :subline_code)
              AND (:state_code IS NULL OR state_code = :state_code)
              AND (:location_code IS NULL OR location_code = :location_code)
            ORDER BY insurer
        """)
        params = {
            "product_code": product_code if product_code else None,
            "subproduct_code": subproduct_code if subproduct_code else None,
            "business_type_code": business_type_code if business_type_code else None,
            "rule_business_variant": rule_business_variant if rule_business_variant else None,
            "subline_code": subline_code if subline_code else None,
            "state_code": state_code if state_code else None,
            "location_code": location_code if location_code else None
        }
        rows = db.execute(sql, params).fetchall()
        return [dict(r._mapping) for r in rows]

    @classmethod
    def perform_rule_lookup(
        cls,
        db: Session,
        req: RuleLookupRequest
    ) -> Tuple[bool, List[Dict[str, str]], Optional[str]]:
        """
        Performs rule lookup with deterministic wildcard fallback precedence:
        Precedence 1: Exact 7-dimension match
        Precedence 2: State-wide location ALL match (e.g. LOC_xx_ALL)
        Precedence 3: Subproduct ALL match (SP_MISC_ALL) if product is PROD_MISC
        """
        # Validate that product and state exist in master tables if provided
        if req.product_code:
            check_prod = db.execute(text("SELECT 1 FROM product_master WHERE product_code = :c"), {"c": req.product_code}).fetchone()
            if not check_prod:
                return False, [], f"Invalid product_code: '{req.product_code}'"

        if req.state_code:
            check_state = db.execute(text("SELECT 1 FROM state_master WHERE state_code = :c"), {"c": req.state_code}).fetchone()
            if not check_state:
                return False, [], f"Invalid state_code: '{req.state_code}'"

        # Check if explicitly provided location code is completely invalid
        if req.location_code and not req.location_code.endswith("_ALL") and req.location_code != "ALL":
            check_loc = db.execute(text("SELECT 1 FROM location_master WHERE location_code = :c"), {"c": req.location_code}).fetchone()
            if not check_loc:
                return False, [], f"Invalid location_code: '{req.location_code}'"

        # --- Precedence 1: Exact Match ---
        results = cls.execute_rule_query(
            db,
            req.product_code,
            req.subproduct_code,
            req.business_type_code,
            req.rule_business_variant,
            req.subline_code,
            req.state_code,
            req.location_code
        )
        if results:
            return True, results, None

        # --- Precedence 2: State-Wide Location Wildcard (e.g., LOC_xx_ALL or location_type='ALL_STATE') ---
        if req.location_code and req.state_code and not req.location_code.endswith("_ALL") and req.location_code != "ALL":
            state_all_sql = text("""
                SELECT location_code
                FROM location_master
                WHERE state_code = :state_code
                  AND (location_type = 'ALL_STATE' OR location_code LIKE '%_ALL' OR source_location = 'ALL')
                LIMIT 1
            """)
            state_all_row = db.execute(state_all_sql, {"state_code": req.state_code}).fetchone()
            if state_all_row:
                wildcard_loc_code = state_all_row.location_code
                results = cls.execute_rule_query(
                    db,
                    req.product_code,
                    req.subproduct_code,
                    req.business_type_code,
                    req.rule_business_variant,
                    req.subline_code,
                    req.state_code,
                    wildcard_loc_code
                )
                if results:
                    return True, results, None

        # --- Precedence 3: Subproduct ALL Wildcard (e.g., SP_MISC_ALL) ---
        if req.product_code == "PROD_MISC" and req.subproduct_code != "SP_MISC_ALL":
            results = cls.execute_rule_query(
                db,
                req.product_code,
                "SP_MISC_ALL",
                req.business_type_code,
                req.rule_business_variant,
                req.subline_code,
                req.state_code,
                req.location_code
            )
            if results:
                return True, results, None

            # Attempt SP_MISC_ALL + Location ALL together
            if req.location_code and req.state_code and not req.location_code.endswith("_ALL") and req.location_code != "ALL":
                state_all_sql = text("""
                    SELECT location_code
                    FROM location_master
                    WHERE state_code = :state_code
                      AND (location_type = 'ALL_STATE' OR location_code LIKE '%_ALL' OR source_location = 'ALL')
                    LIMIT 1
                """)
                state_all_row = db.execute(state_all_sql, {"state_code": req.state_code}).fetchone()
                if state_all_row:
                    results = cls.execute_rule_query(
                        db,
                        req.product_code,
                        "SP_MISC_ALL",
                        req.business_type_code,
                        req.rule_business_variant,
                        req.subline_code,
                        req.state_code,
                        state_all_row.location_code
                    )
                    if results:
                        return True, results, None

        # No match found
        return False, [], "No matching rule found for the given parameters"

    @classmethod
    def standardize_raw_input(
        cls,
        db: Session,
        raw: RawInflowLookupRequest
    ) -> Tuple[Optional[StandardizedCodesInfo], Optional[str]]:
        """
        Resolves user-entered raw strings into standardized internal codes using mapping tables.
        Also validates state-location relationship.
        """
        raw_prod = raw.product.strip() if raw.product else None
        raw_subprod = raw.subproduct.strip() if raw.subproduct else None
        raw_bt = raw.business_type.strip() if raw.business_type else None
        raw_subline = raw.subline.strip() if raw.subline else None
        raw_state = raw.state.strip() if raw.state else None
        raw_loc = raw.location.strip() if raw.location else None

        std_product_code = None
        std_subproduct_code = None
        std_subline_code = None
        std_state_code = None
        std_location_code = None
        std_business_type_code = None
        std_variant = None

        # -----------------------------------------------------------
        # 1. Product Standardization
        # -----------------------------------------------------------
        if raw_prod:
            prod_sql = text("""
                SELECT product_code FROM product_mapping WHERE UPPER(TRIM(original_value)) = UPPER(:val)
                UNION
                SELECT product_code FROM product_master WHERE UPPER(TRIM(product_name)) = UPPER(:val) OR UPPER(TRIM(product_code)) = UPPER(:val)
                LIMIT 1
            """)
            prod_row = db.execute(prod_sql, {"val": raw_prod}).fetchone()
            if not prod_row:
                return None, f"Product mapping not found for '{raw.product}'"
            std_product_code = prod_row.product_code

        # -----------------------------------------------------------
        # 2. SubLine Standardization
        # -----------------------------------------------------------
        if raw_subline:
            subline_sql = text("""
                SELECT subline_code FROM subline_mapping WHERE UPPER(TRIM(original_value)) = UPPER(:val) OR UPPER(TRIM(ui_display_value)) = UPPER(:val)
                UNION
                SELECT subline_code FROM subline_master WHERE UPPER(TRIM(source_subline)) = UPPER(:val) OR UPPER(TRIM(ui_display_value)) = UPPER(:val) OR UPPER(TRIM(subline_code)) = UPPER(:val)
                LIMIT 1
            """)
            subline_row = db.execute(subline_sql, {"val": raw_subline}).fetchone()
            if not subline_row:
                return None, f"SubLine mapping not found for '{raw.subline}'"
            std_subline_code = subline_row.subline_code

        # -----------------------------------------------------------
        # 3. SubProduct Standardization (Product-Scoped)
        # -----------------------------------------------------------
        if raw_subprod:
            subprod_sql = text("""
                SELECT subproduct_code FROM subproduct_mapping WHERE (:prod_code IS NULL OR product_code = :prod_code) AND (UPPER(TRIM(original_value)) = UPPER(:val) OR UPPER(TRIM(subproduct_code)) = UPPER(:val))
                UNION
                SELECT subproduct_code FROM subproduct_master WHERE (:prod_code IS NULL OR product_code = :prod_code) AND (UPPER(TRIM(subproduct_name)) = UPPER(:val) OR UPPER(TRIM(subproduct_code)) = UPPER(:val))
                LIMIT 1
            """)
            subprod_row = db.execute(subprod_sql, {"prod_code": std_product_code, "val": raw_subprod}).fetchone()
            if not subprod_row:
                return None, f"SubProduct mapping not found for '{raw.subproduct}'"
            std_subproduct_code = subprod_row.subproduct_code

        # -----------------------------------------------------------
        # 4. State Standardization
        # -----------------------------------------------------------
        if raw_state:
            clean_state_norm = raw_state.upper().replace(" ", "").replace("A", "")
            state_sql = text("""
                SELECT state_code FROM state_mapping
                WHERE UPPER(TRIM(source_state)) = UPPER(:val)
                   OR UPPER(TRIM(ui_display_value)) = UPPER(:val)
                   OR UPPER(TRIM(state_code)) = UPPER(:val)
                   OR REPLACE(REPLACE(UPPER(source_state), ' ', ''), 'A', '') = :norm_val
                UNION
                SELECT state_code FROM state_master
                WHERE UPPER(TRIM(source_state)) = UPPER(:val)
                   OR UPPER(TRIM(ui_display_value)) = UPPER(:val)
                   OR UPPER(TRIM(state_code)) = UPPER(:val)
                   OR REPLACE(REPLACE(UPPER(source_state), ' ', ''), 'A', '') = :norm_val
                LIMIT 1
            """)
            state_row = db.execute(state_sql, {"val": raw_state, "norm_val": clean_state_norm}).fetchone()
            if not state_row:
                return None, f"State mapping not found for '{raw.state}'"
            std_state_code = state_row.state_code

        # -----------------------------------------------------------
        # 5. Location Standardization & State Relationship Validation
        # -----------------------------------------------------------
        if raw_loc:
            loc_sql = text("""
                SELECT location_code, state_code FROM location_mapping WHERE UPPER(TRIM(source_location)) = UPPER(:val) OR UPPER(TRIM(ui_display_value)) = UPPER(:val) OR UPPER(TRIM(location_code)) = UPPER(:val)
                UNION
                SELECT location_code, state_code FROM location_master WHERE UPPER(TRIM(source_location)) = UPPER(:val) OR UPPER(TRIM(ui_display_value)) = UPPER(:val) OR UPPER(TRIM(location_code)) = UPPER(:val)
            """)
            loc_rows = db.execute(loc_sql, {"val": raw_loc}).fetchall()
            if not loc_rows:
                return None, f"Location mapping not found for '{raw.location}'"

            if std_state_code:
                matching_loc = None
                for lr in loc_rows:
                    if lr.state_code == std_state_code:
                        matching_loc = lr
                        break
                if not matching_loc:
                    actual_state_code = loc_rows[0].state_code
                    return None, f"Location '{raw.location}' does not belong to selected state '{raw.state}' (belongs to state code '{actual_state_code}')"
                std_location_code = matching_loc.location_code
            else:
                std_location_code = loc_rows[0].location_code

        # -----------------------------------------------------------
        # 6. Business Type & Variant Standardization
        # -----------------------------------------------------------
        if raw_bt:
            bt_sql = text("""
                SELECT business_type_code, source_rule_value, applicable_subline_code
                FROM business_type_mapping
                WHERE UPPER(TRIM(ui_display_value)) = UPPER(:val)
                   OR UPPER(TRIM(source_rule_value)) = UPPER(:val)
                   OR UPPER(TRIM(business_type_code)) = UPPER(:val)
            """)
            bt_rows = db.execute(bt_sql, {"val": raw_bt}).fetchall()
            if not bt_rows:
                return None, f"Business Type mapping not found for '{raw.business_type}'"

            std_business_type_code = bt_rows[0].business_type_code

            if raw.rule_business_variant:
                std_variant = raw.rule_business_variant.strip()
            else:
                if std_business_type_code == "BT_RO_RN":
                    std_variant = "RO/RN"
                elif std_business_type_code == "BT_NEW":
                    if std_product_code == "PROD_2W":
                        std_variant = "NEW(1+5)"
                    else:
                        std_variant = "NEW(1+3)"
                else:
                    std_variant = bt_rows[0].source_rule_value

        std_info = StandardizedCodesInfo(
            product_code=std_product_code or "",
            subproduct_code=std_subproduct_code or "",
            business_type_code=std_business_type_code or "",
            rule_business_variant=std_variant or "",
            subline_code=std_subline_code or "",
            state_code=std_state_code or "",
            location_code=std_location_code or ""
        )

        return std_info, None

        return std_info, None
