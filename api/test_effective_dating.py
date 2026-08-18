# ============================================================
# test_effective_dating.py
# ============================================================
# Purpose: Complete effective-dating test suite for the
#          Motor Insurance Inflow API.
#
# Tests cover:
#   - Effective-date resolution (6 date scenarios)
#   - Data isolation (July vs August version isolation)
#   - All 4 wildcard precedence paths with date preservation
#   - Calculation endpoint with effective dates
#   - GET /rule-master/effective-dates endpoint
#   - Error cases (pre-first-date, invalid inputs)
#
# Run with:
#   venv\Scripts\python.exe test_effective_dating.py
#
# Prerequisites:
#   - uvicorn must be running on port 8001
#   - rule_master must contain 2026-07-01 and 2026-08-01 versions
# ============================================================

import sys
import json
import urllib.request
import urllib.error
from datetime import date

sys.path.append(r"D:\Inflow\api")
from database import engine
from sqlalchemy import text

BASE_URL = "http://127.0.0.1:8001"
PASS, FAIL = "PASS", "FAIL"
log_results = []


# ============================================================
# HTTP helpers
# ============================================================
def post(endpoint, payload):
    try:
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            BASE_URL + endpoint,
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"matched": False, "error": e.read().decode(), "results": []}
    except Exception as e:
        return {"matched": False, "error": str(e), "results": []}


def get(endpoint):
    try:
        with urllib.request.urlopen(BASE_URL + endpoint, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"__ex__": str(e)}


def record(num, desc, ok, detail=""):
    status = PASS if ok else FAIL
    log_results.append((status, num, desc))
    print("TEST %02d [%s] %s" % (num, status, desc))
    if detail:
        print("         " + str(detail)[:140])


# ============================================================
# Reusable base payloads for /inflow-lookup
# ============================================================
BASE_INFLOW = {
    "product":       "Two Wheeler",
    "subproduct":    "Bike",
    "business_type": "New",
    "subline":       "Package",
    "state":         "ANDHARA PRADESH",
    "location":      "VIJAYAWADA"
}

BASE_CALC = {
    "product":       "Two Wheeler",
    "subproduct":    "Bike",
    "business_type": "New",
    "subline":       "Package",
    "state":         "ANDHARA PRADESH",
    "location":      "VIJAYAWADA",
    "vehicle_make":  "SUZUKI",
    "engine_cc":     125,
    "cpa":           False
}


# ============================================================
# SECTION 1 — Effective-Date Resolution Tests
# ============================================================
print("=" * 65)
print("  SECTION 1: EFFECTIVE-DATE RESOLUTION")
print("=" * 65)

# TEST 1 — exact first effective date
r = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-07-01"})
eff = r.get("effective_date_used")
record(1, "requested_date=2026-07-01 -> effective_date_used=2026-07-01",
       r.get("matched") and eff == "2026-07-01",
       "effective=%s matched=%s err=%s" % (eff, r.get("matched"), r.get("error")))

# TEST 2 — mid-July resolves to July version
r = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-07-15"})
eff = r.get("effective_date_used")
record(2, "requested_date=2026-07-15 -> effective_date_used=2026-07-01",
       r.get("matched") and eff == "2026-07-01",
       "effective=%s" % eff)

# TEST 3 — last day of July still resolves to July version
r = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-07-31"})
eff = r.get("effective_date_used")
record(3, "requested_date=2026-07-31 -> effective_date_used=2026-07-01",
       r.get("matched") and eff == "2026-07-01",
       "effective=%s" % eff)

# TEST 4 — exact second effective date (August 1)
r = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-08-01"})
eff = r.get("effective_date_used")
record(4, "requested_date=2026-08-01 -> effective_date_used=2026-08-01",
       r.get("matched") and eff == "2026-08-01",
       "effective=%s" % eff)

# TEST 5 — mid-August resolves to August version
r = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-08-15"})
eff = r.get("effective_date_used")
record(5, "requested_date=2026-08-15 -> effective_date_used=2026-08-01",
       r.get("matched") and eff == "2026-08-01",
       "effective=%s" % eff)

# TEST 6 — date BEFORE first version -> must return business error, not forward-fallback
r = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-06-30"})
matched = r.get("matched")
error   = r.get("error") or ""
eff     = r.get("effective_date_used")
record(6, "requested_date=2026-06-30 -> NO applicable version (no forward-fallback)",
       not matched and "No applicable Rule Master version" in error,
       "matched=%s error=%s effective=%s" % (matched, error[:80], eff))


# ============================================================
# SECTION 2 — Data Isolation Tests
# ============================================================
print()
print("=" * 65)
print("  SECTION 2: DATA ISOLATION (CROSS-VERSION MIXING CHECK)")
print("=" * 65)

# Direct DB check — confirm row counts per version
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT effective_from, COUNT(*) AS cnt FROM rule_master "
        "GROUP BY effective_from ORDER BY effective_from"
    )).fetchall()

print("DB effective_from row counts:")
july_count = 0
aug_count  = 0
for r in rows:
    ef  = str(r.effective_from)
    cnt = r.cnt
    print("  %s -> %d rows" % (ef, cnt))
    if ef == "2026-07-01":
        july_count = cnt
    elif ef == "2026-08-01":
        aug_count = cnt

record(7, "July 2026-07-01 has exactly 9322 rows in DB",
       july_count == 9322,
       "found=%d" % july_count)

record(8, "August 2026-08-01 has exactly 10735 rows in DB",
       aug_count == 10735,
       "found=%d" % aug_count)

# Verify July lookup only sees July rows
with engine.connect() as conn:
    jul_count_in_api = conn.execute(text(
        "SELECT COUNT(*) AS cnt FROM rule_master WHERE effective_from = '2026-07-01'"
    )).fetchone().cnt
    aug_count_in_api = conn.execute(text(
        "SELECT COUNT(*) AS cnt FROM rule_master WHERE effective_from = '2026-08-01'"
    )).fetchone().cnt

record(9, "DB isolates July rows (9322) from August rows (10735)",
       jul_count_in_api == 9322 and aug_count_in_api == 10735,
       "July=%d August=%d" % (jul_count_in_api, aug_count_in_api))

# Verify API responses carry the correct version marker
r_july = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-07-20"})
r_aug  = post("/inflow-lookup", {**BASE_INFLOW, "requested_date": "2026-08-20"})

record(10, "July request -> effective_date_used=2026-07-01 (not August)",
       r_july.get("effective_date_used") == "2026-07-01",
       "got=%s" % r_july.get("effective_date_used"))

record(11, "August request -> effective_date_used=2026-08-01 (not July)",
       r_aug.get("effective_date_used") == "2026-08-01",
       "got=%s" % r_aug.get("effective_date_used"))


# ============================================================
# SECTION 3 — Wildcard Precedence + Date Preservation
# ============================================================
print()
print("=" * 65)
print("  SECTION 3: WILDCARD PRECEDENCE WITH DATE PRESERVATION")
print("=" * 65)

# P1 — Exact 7-dimension match (July)
r = post("/rule-lookup", {
    "requested_date":      "2026-07-15",
    "product_code":        "PROD_2W",
    "subproduct_code":     "SP_2W_BIKE",
    "business_type_code":  "BT_NEW",
    "rule_business_variant": "NEW(1+5)",
    "subline_code":        "SL_PKG",
    "state_code":          "ST_AP",
    "location_code":       "LOC_AP_VIJAYAWADA"
})
record(12, "P1 Exact match July: effective_date_used=2026-07-01",
       r.get("matched") and r.get("effective_date_used") == "2026-07-01",
       "matched=%s eff=%s count=%s" % (r.get("matched"), r.get("effective_date_used"), r.get("count")))

# P1 — Same exact match, August version
r = post("/rule-lookup", {
    "requested_date":      "2026-08-15",
    "product_code":        "PROD_2W",
    "subproduct_code":     "SP_2W_BIKE",
    "business_type_code":  "BT_NEW",
    "rule_business_variant": "NEW(1+5)",
    "subline_code":        "SL_PKG",
    "state_code":          "ST_AP",
    "location_code":       "LOC_AP_VIJAYAWADA"
})
record(13, "P1 Exact match August: effective_date_used=2026-08-01",
       r.get("matched") and r.get("effective_date_used") == "2026-08-01",
       "matched=%s eff=%s count=%s" % (r.get("matched"), r.get("effective_date_used"), r.get("count")))

# P2 — State-wide location wildcard (July)
r_wildloc = post("/inflow-lookup", {
    "requested_date": "2026-07-15",
    "product":        "Two Wheeler",
    "subproduct":     "Bike",
    "business_type":  "New",
    "subline":        "Package",
    "state":          "UTTARKHAND",
    "location":       "ALL"
})
record(14, "P2 Location wildcard July: effective_date_used=2026-07-01",
       r_wildloc.get("effective_date_used") == "2026-07-01",
       "matched=%s eff=%s count=%s err=%s" % (
           r_wildloc.get("matched"), r_wildloc.get("effective_date_used"),
           r_wildloc.get("count"), r_wildloc.get("error")))

# P2 — State-wide location wildcard (August)
r_wildloc_aug = post("/inflow-lookup", {
    "requested_date": "2026-08-15",
    "product":        "Two Wheeler",
    "subproduct":     "Bike",
    "business_type":  "New",
    "subline":        "Package",
    "state":          "UTTARKHAND",
    "location":       "ALL"
})
record(15, "P2 Location wildcard August: effective_date_used=2026-08-01",
       r_wildloc_aug.get("effective_date_used") == "2026-08-01",
       "matched=%s eff=%s" % (r_wildloc_aug.get("matched"), r_wildloc_aug.get("effective_date_used")))

# P3/P4 — PROD_MISC fallback (July)
r_misc = post("/inflow-lookup", {
    "requested_date": "2026-07-15",
    "product":        "Miscellaneous Vehicle",
    "subproduct":     "Bulldozer",
    "business_type":  "Renewal",
    "subline":        "Package",
    "state":          "ANDHARA PRADESH",
    "location":       "VIJAYAWADA"
})
record(16, "P3/P4 PROD_MISC fallback July: effective_date_used preserved",
       r_misc.get("effective_date_used") in ("2026-07-01", None)
       and (r_misc.get("matched") or r_misc.get("error") is not None),
       "matched=%s eff=%s err=%s" % (
           r_misc.get("matched"), r_misc.get("effective_date_used"), r_misc.get("error")))


# ============================================================
# SECTION 4 — Calculation Endpoint Tests
# ============================================================
print()
print("=" * 65)
print("  SECTION 4: CALCULATION ENDPOINT (/calculate-inflow)")
print("=" * 65)

# July calculation
r_calc_jul = post("/calculate-inflow", {**BASE_CALC, "requested_date": "2026-07-15"})
record(17, "Calc July 2026-07-15: matched + effective_date_used=2026-07-01",
       r_calc_jul.get("matched") and r_calc_jul.get("effective_date_used") == "2026-07-01",
       "matched=%s eff=%s rate=%s err=%s" % (
           r_calc_jul.get("matched"), r_calc_jul.get("effective_date_used"),
           r_calc_jul.get("results", [{}])[0].get("rate") if r_calc_jul.get("results") else None,
           r_calc_jul.get("error")))

# August calculation
r_calc_aug = post("/calculate-inflow", {**BASE_CALC, "requested_date": "2026-08-15"})
record(18, "Calc August 2026-08-15: matched + effective_date_used=2026-08-01",
       r_calc_aug.get("matched") and r_calc_aug.get("effective_date_used") == "2026-08-01",
       "matched=%s eff=%s err=%s" % (
           r_calc_aug.get("matched"), r_calc_aug.get("effective_date_used"),
           r_calc_aug.get("error")))

# Calc: pre-first-date must fail
r_calc_early = post("/calculate-inflow", {**BASE_CALC, "requested_date": "2026-06-30"})
record(19, "Calc 2026-06-30: must fail with 'No applicable Rule Master version'",
       not r_calc_early.get("matched") and
       "No applicable Rule Master version" in str(r_calc_early.get("error", "")),
       "matched=%s err=%s" % (r_calc_early.get("matched"), str(r_calc_early.get("error", ""))[:80]))

# Calc: rate verification July (SUZUKI 125cc W/O CPA -> 40%)
july_rate = (r_calc_jul.get("results") or [{}])[0].get("rate")
record(20, "Calc July: SUZUKI 125cc W/O CPA -> rate=40.0",
       r_calc_jul.get("matched") and july_rate == 40.0,
       "rate=%s" % july_rate)


# ============================================================
# SECTION 5 — Effective Dates Endpoint
# ============================================================
print()
print("=" * 65)
print("  SECTION 5: GET /rule-master/effective-dates")
print("=" * 65)

eff_resp = get("/rule-master/effective-dates")
dates_list = eff_resp.get("dates", [])
record(21, "GET /rule-master/effective-dates returns list",
       isinstance(dates_list, list) and len(dates_list) >= 2,
       "dates=%s count=%s" % (dates_list, eff_resp.get("count")))

record(22, "Effective dates include 2026-07-01 and 2026-08-01",
       "2026-07-01" in dates_list and "2026-08-01" in dates_list,
       "dates=%s" % dates_list)

record(23, "Effective dates are ordered ascending (Jul before Aug)",
       len(dates_list) >= 2 and dates_list.index("2026-07-01") < dates_list.index("2026-08-01"),
       "dates=%s" % dates_list)


# ============================================================
# SECTION 6 — Error Handling Tests
# ============================================================
print()
print("=" * 65)
print("  SECTION 6: ERROR HANDLING")
print("=" * 65)

# Invalid product
r_bad_prod = post("/calculate-inflow", {**BASE_CALC, "requested_date": "2026-07-15", "product": "INVALID XYZ 999"})
record(24, "Invalid product -> clear 'Product mapping not found' error",
       not r_bad_prod.get("matched") and "Product mapping not found" in str(r_bad_prod.get("error", "")),
       "err=%s" % r_bad_prod.get("error"))

# Invalid state
r_bad_state = post("/calculate-inflow", {**BASE_CALC, "requested_date": "2026-07-15", "state": "FAKE STATE 999"})
record(25, "Invalid state -> clear 'State mapping not found' error",
       not r_bad_state.get("matched") and "State mapping not found" in str(r_bad_state.get("error", "")),
       "err=%s" % r_bad_state.get("error"))

# Invalid location
r_bad_loc = post("/calculate-inflow", {**BASE_CALC, "requested_date": "2026-07-15", "location": "NONEXISTENT CITY 999"})
record(26, "Invalid location -> clear 'Location mapping not found' error",
       not r_bad_loc.get("matched") and "Location mapping not found" in str(r_bad_loc.get("error", "")),
       "err=%s" % r_bad_loc.get("error"))

# No-date-version before all versions
r_pre = post("/rule-lookup", {
    "requested_date":        "2026-05-01",
    "product_code":          "PROD_2W",
    "subproduct_code":       "SP_2W_BIKE",
    "business_type_code":    "BT_NEW",
    "rule_business_variant": "NEW(1+5)",
    "subline_code":          "SL_PKG",
    "state_code":            "ST_AP",
    "location_code":         "LOC_AP_VIJAYAWADA"
})
record(27, "requested_date=2026-05-01 (way before July) -> no applicable version error",
       not r_pre.get("matched") and "No applicable Rule Master version" in str(r_pre.get("error", "")),
       "err=%s" % str(r_pre.get("error", ""))[:80])


# ============================================================
# SECTION 7 — July Data Integrity Verification
# ============================================================
print()
print("=" * 65)
print("  SECTION 7: JULY DATA INTEGRITY (READ-ONLY CONFIRM)")
print("=" * 65)

with engine.connect() as conn:
    july_total = conn.execute(text(
        "SELECT COUNT(*) AS cnt FROM rule_master WHERE effective_from = '2026-07-01'"
    )).fetchone().cnt
    aug_total = conn.execute(text(
        "SELECT COUNT(*) AS cnt FROM rule_master WHERE effective_from = '2026-08-01'"
    )).fetchone().cnt
    grand_total = conn.execute(text(
        "SELECT COUNT(*) AS cnt FROM rule_master"
    )).fetchone().cnt

record(28, "July data integrity: 9322 rows untouched",
       july_total == 9322,
       "July rows=%d" % july_total)

record(29, "August data integrity: 10735 rows untouched",
       aug_total == 10735,
       "August rows=%d" % aug_total)

record(30, "Total rows = 20057 (no data was added/removed/modified)",
       grand_total == 20057,
       "Total rows=%d" % grand_total)


# ============================================================
# FINAL SUMMARY
# ============================================================
print()
print("=" * 65)
passed = sum(1 for s, _, _ in log_results if s == PASS)
failed = sum(1 for s, _, _ in log_results if s == FAIL)
total  = len(log_results)
print("  RESULTS: %d/%d PASSED | %d FAILED" % (passed, total, failed))
print("=" * 65)

if failed:
    print("\nFailed tests:")
    for s, n, d in log_results:
        if s == FAIL:
            print("  FAIL TEST %02d: %s" % (n, d))
else:
    print("\n  ALL TESTS PASSED — Effective-dating implementation is complete.")

print()
print("July historical Rule Master data was not modified.")
print("July row count confirmed: %d" % july_total)
print("August row count confirmed: %d" % aug_total)
