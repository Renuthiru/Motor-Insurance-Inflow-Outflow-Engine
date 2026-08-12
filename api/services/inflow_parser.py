# ============================================================
# services/inflow_parser.py
# ============================================================
# Purpose: Parses RULE_MASTER.inflow text expressions into
#          structured rule objects for the calculation engine.
#
# KEY INSIGHT from real DB analysis:
#   Each segment starts with: RATE%{CONDITION_TEXT
#   e.g. 40.00%{NT(W/O CPA -2% Less - SUZUKI - Upto 150cc)
#
#   The "-2%" inside the condition text is NOT a rate.
#   The pattern RATE%{ (percent followed by open-brace) marks
#   the start of a new segment, not arbitrary %  occurrences.
# ============================================================

import re
from typing import List, Dict, Any


class InflowParser:

    # Regex: matches a rate number followed by %{ which signals a new segment
    # e.g. "40.00%{" or "47.50%{"  — NOT "-2%" or "2% Less"
    SEGMENT_SPLIT_RE = re.compile(r"(\d+(?:\.\d+)?)%\{")

    @staticmethod
    def parse_expression(expr: str) -> List[Dict[str, Any]]:
        """
        Parses an inflow expression string from rule_master.inflow.

        Format from DB:
          40.00%{NT(W/O CPA -2% Less - SUZUKI - Upto 150cc),38.50%{NT(W/O CPA -2% Less - Hero - Upto 150cc)}

        Each segment: RATE%{CONDITION_TEXT

        Returns list of dicts with:
          rate, coverage, cpa, cc_min, cc_max, gvw_min, gvw_max,
          allowed_makes, exclude_models, age_min, age_max, raw
        """
        if not expr:
            return []

        # Split expression into (rate, condition_text) pairs
        # Pattern: number followed by %{ starts a new segment
        parts = InflowParser.SEGMENT_SPLIT_RE.split(expr)
        # parts = ['', '40.00', 'NT(W/O CPA...),', '38.50', 'NT(...)']
        # First element is empty string before first match
        # Then alternates: rate_string, condition_text, rate_string, condition_text...

        segments = []
        idx = 1  # skip empty first element
        while idx < len(parts) - 1:
            rate_str = parts[idx]
            cond_text = parts[idx + 1]
            idx += 2

            try:
                rate = float(rate_str)
            except ValueError:
                continue

            # Clean trailing comma, closing brace, whitespace from condition text
            cond_clean = cond_text.strip()
            if cond_clean.endswith("}"):
                cond_clean = cond_clean[:-1]
            if cond_clean.endswith(","):
                cond_clean = cond_clean[:-1]
            # Remove trailing closing paren if present from last segment
            cond_clean = cond_clean.strip()

            seg = InflowParser._parse_condition(rate, cond_clean)
            segments.append(seg)

        # Fallback: if no %{ segments found, try simple flat rate (e.g. "47.50%{NT")
        if not segments:
            simple = re.match(r"(\d+(?:\.\d+)?)%\{?(\w+)\}?", expr.strip())
            if simple:
                rate = float(simple.group(1))
                cond_clean = simple.group(2)
                segments.append(InflowParser._parse_condition(rate, cond_clean))

        return segments

    @staticmethod
    def _parse_condition(rate: float, cond_clean: str) -> Dict[str, Any]:
        """
        Parses the condition text of a single segment and returns a structured dict.
        """
        cond_upper = cond_clean.upper()

        # 1. Coverage type (NT = Net/Total, OD = Own Damage, ALL = unspecified)
        coverage = "ALL"
        if cond_upper.startswith("NT") or "(NT" in cond_upper or "NT(" in cond_upper:
            coverage = "NT"
        elif cond_upper.startswith("OD") or "(OD" in cond_upper or "OD(" in cond_upper:
            coverage = "OD"

        # 2. CPA status — "W/O CPA" means WITHOUT CPA → cpa=False
        cpa = None
        if any(term in cond_upper for term in ["W/O CPA", "WITHOUT CPA", "W/0 CPA"]):
            cpa = False
        elif "WITH CPA" in cond_upper:
            cpa = True
        # Note: "CPA" alone in condition text without W/O means not clearly defined
        # We only set cpa=True when explicitly stated as "WITH CPA"

        # 3. Engine CC parsing (case insensitive "cc" or "CC")
        cc_min = None
        cc_max = None

        # Patterns supported (from real DB data):
        #   >150cc-350cc  (range, lowercase cc)
        #   Above 1000CC to 1500CC  (range, uppercase CC)
        #   Upto 150cc  (upper bound)
        #   <125CC  (upper bound)
        #   Above 1500CC  (lower bound, unbounded)

        # Range: "X cc - Y cc" or "Xcc-Ycc" or "Above X to Y CC"
        cc_range = re.search(
            r"(?:Above|>)?\s*(\d+)\s*(?:CC|cc)\s*[-to]+\s*(\d+)\s*(?:CC|cc)",
            cond_clean, re.IGNORECASE
        )
        if not cc_range:
            # Also match: ">150cc-350cc" without space
            cc_range = re.search(
                r">(\d+)\s*(?:CC|cc)-(\d+)\s*(?:CC|cc)",
                cond_clean, re.IGNORECASE
            )
        if not cc_range:
            # "Above 1000CC to 1500CC"
            cc_range = re.search(
                r"Above\s+(\d+)\s*(?:CC|cc)\s+to\s+(\d+)\s*(?:CC|cc)",
                cond_clean, re.IGNORECASE
            )

        if cc_range:
            cc_min = int(cc_range.group(1))
            cc_max = int(cc_range.group(2))
        else:
            # Upto / <= / <
            cc_upto = re.search(
                r"(?:Upto|<=|<)\s*(\d+)\s*(?:CC|cc)",
                cond_clean, re.IGNORECASE
            )
            if cc_upto:
                cc_min = 0
                cc_max = int(cc_upto.group(1))
            else:
                # Above / >
                cc_above = re.search(
                    r"(?:Above|>)\s*(\d+)\s*(?:CC|cc)",
                    cond_clean, re.IGNORECASE
                )
                if cc_above:
                    cc_min = int(cc_above.group(1))
                    cc_max = 999999

        # 4. GVW parsing (Ton / Tons / K Ton)
        # Only parse GVW when "Ton" or "TON" appears in the condition
        gvw_min = None
        gvw_max = None

        if "TON" in cond_upper:
            # Range: "Above 43K to 47.5K Ton" or ">20 <=35k TON" or "Upto 3.0Ton"
            gvw_range = re.search(
                r"(?:Above|>)?\s*(\d+(?:\.\d+)?)\s*(?:K|k)?\s*(?:to|<=|-)\s*(\d+(?:\.\d+)?)\s*(?:K|k)?\s*(?:Ton|TON)",
                cond_clean
            )
            if gvw_range:
                scale = 1000 if ("K" in cond_clean or "k" in cond_clean) else 1
                gvw_min = float(gvw_range.group(1)) * scale
                gvw_max = float(gvw_range.group(2)) * scale
            else:
                gvw_upto = re.search(
                    r"(?:Upto|<=|<)\s*(\d+(?:\.\d+)?)\s*(?:K|k)?\s*(?:Ton|TON)",
                    cond_clean, re.IGNORECASE
                )
                if gvw_upto:
                    scale = 1000 if ("K" in cond_clean or "k" in cond_clean) else 1
                    gvw_max = float(gvw_upto.group(1)) * scale
                else:
                    gvw_above = re.search(
                        r"(?:Above|>)\s*(\d+(?:\.\d+)?)\s*(?:K|k)?\s*(?:Ton|TON)",
                        cond_clean, re.IGNORECASE
                    )
                    if gvw_above:
                        scale = 1000 if ("K" in cond_clean or "k" in cond_clean) else 1
                        gvw_min = float(gvw_above.group(1)) * scale

        # 5. Vehicle Make / Brand detection
        # Known brands from real DB data
        known_brands = [
            "SUZUKI", "HERO", "TVS", "YAMAHA", "HONDA", "BAJAJ",
            "TATA", "MAHINDRA", "MARUTI", "HARVESTOR", "LIBERTY",
            "ROYAL ENFIELD", "ENFIELD"
        ]
        allowed_makes = []
        for brand in known_brands:
            if brand in cond_upper:
                allowed_makes.append(brand)

        # 6. Excluded model detection (e.g., "Except Bolero")
        exclude_models = []
        exc_match = re.search(r"Except\s+(\w+)", cond_clean, re.IGNORECASE)
        if exc_match:
            exclude_models.append(exc_match.group(1).upper())

        # 7. Fuel type (petrol / diesel)
        fuel_type = None
        if "PETROL" in cond_upper:
            fuel_type = "PETROL"
        elif "DIESEL" in cond_upper:
            fuel_type = "DIESEL"

        # 8. Vehicle Age parsing
        age_min = None
        age_max = None

        age_upto = re.search(
            r"(?:<=|<)\s*(\d+)\s*(?:Yr|yr|Yrs|yrs)",
            cond_clean, re.IGNORECASE
        )
        if age_upto:
            age_min = 0
            age_max = int(age_upto.group(1))
        else:
            age_above = re.search(
                r"(?:>)\s*(\d+)\s*(?:Yr|yr|Yrs|yrs)",
                cond_clean, re.IGNORECASE
            )
            if age_above:
                age_min = int(age_above.group(1))
                age_max = 99

        return {
            "rate": rate,
            "coverage": coverage,
            "cpa": cpa,
            "cc_min": cc_min,
            "cc_max": cc_max,
            "gvw_min": gvw_min,
            "gvw_max": gvw_max,
            "allowed_makes": allowed_makes,
            "exclude_models": exclude_models,
            "fuel_type": fuel_type,
            "age_min": age_min,
            "age_max": age_max,
            "raw": cond_clean
        }
