"""
============================================================
audit_combinations.py
Complete Rule Master Combination Audit
============================================================
STEP 1: Inspect all master/mapping tables
STEP 2: Trace the exact broken GCV RO/RN case
STEP 3: Verify RO/RN specifically
STEP 4: Audit ALL business types
STEP 5: Automated rule_master coverage test
STEP 6: Wildcard audit
STEP 7: All products audit
============================================================
"""

import sys
import os
import json
import urllib.request
from dotenv import load_dotenv
import pymysql

load_dotenv()

# ── DB Connection ──────────────────────────────────────────
conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "inflow_db"),
    charset="utf8mb4"
)
cur = conn.cursor(pymysql.cursors.DictCursor)

BASE = "http://127.0.0.1:8001"

def q(sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()

def api_post(endpoint, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + endpoint, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return None, f"HTTP {e.code}: {body[:300]}"
    except Exception as ex:
        return None, str(ex)

sep = lambda w=70: print("=" * w)
hdr = lambda t: (sep(), print(f"  {t}"), sep())

# ════════════════════════════════════════════════════════════
# STEP 1 — INSPECT ALL MASTER / MAPPING TABLES
# ════════════════════════════════════════════════════════════
hdr("STEP 1: MASTER / MAPPING TABLE INSPECTION")

# 1A. Business Type Master
print("\n── business_type_master ──")
bts = q("SELECT * FROM business_type_master ORDER BY business_type_code")
for r in bts:
    print(f"  code={r['business_type_code']} | canonical={r.get('canonical_business_type')} | ui={r.get('ui_display_value')} | active={r.get('is_active')}")

# 1B. Business Type Mapping
print("\n── business_type_mapping ──")
btm = q("SELECT * FROM business_type_mapping ORDER BY mapping_id")
for r in btm:
    print(f"  id={r['mapping_id']} | code={r['business_type_code']} | ui_display={r.get('ui_display_value')} | source_rule={r.get('source_rule_value')} | subline={r.get('applicable_subline_code')} | type={r.get('mapping_type')} | active={r.get('is_active')}")

# 1C. Distinct rule_business_variant values in rule_master
print("\n── DISTINCT rule_business_variant in rule_master ──")
variants = q("SELECT DISTINCT rule_business_variant, COUNT(*) as cnt FROM rule_master GROUP BY rule_business_variant ORDER BY rule_business_variant")
for r in variants:
    print(f"  variant='{r['rule_business_variant']}' | rows={r['cnt']}")

# 1D. Distinct business_type_code values in rule_master
print("\n── DISTINCT business_type_code in rule_master ──")
btcodes = q("SELECT DISTINCT business_type_code, COUNT(*) as cnt FROM rule_master GROUP BY business_type_code ORDER BY business_type_code")
for r in btcodes:
    print(f"  bt_code='{r['business_type_code']}' | rows={r['cnt']}")

# 1E. Product master
print("\n── product_master ──")
prods = q("SELECT product_code, product_name FROM product_master ORDER BY product_code")
for r in prods:
    print(f"  {r['product_code']} | {r['product_name']}")

# 1F. SubLine master
print("\n── subline_master ──")
sl = q("SELECT subline_code, source_subline, ui_display_value FROM subline_master")
for r in sl:
    print(f"  {r['subline_code']} | {r['source_subline']} | {r['ui_display_value']}")

# ════════════════════════════════════════════════════════════
# STEP 2 — TRACE BROKEN CASE: GCV / 4W-12000-20000 / RO/RN
# ════════════════════════════════════════════════════════════
hdr("STEP 2: TRACE BROKEN CASE")

print("\nPayload the frontend would send:")
broken_payload = {
    "product":       "Goods Carrying Vehicle",
    "subproduct":    "4W - 12000 TO 20000 GVW",
    "business_type": "Renewal / Rollover",
    "subline":       "Package",
    "state":         "ANDHRA PRADESH",
    "location":      "VIJAYAWADA",
    "vehicle_make":  None,
    "vehicle_model": None,
    "engine_cc":     None,
    "gvw":           None,
    "cpa":           None,
    "vehicle_age":   None,
    "coverage":      None,
    "rule_business_variant": None
}
print(json.dumps(broken_payload, indent=2))

print("\n── Calling POST /calculate-inflow ──")
result, err = api_post("/calculate-inflow", broken_payload)
print(f"  Result: {json.dumps(result, indent=2) if result else 'ERROR: ' + str(err)}")

# ════════════════════════════════════════════════════════════
# STEP 3 — RO/RN SPECIFIC INVESTIGATION
# ════════════════════════════════════════════════════════════
hdr("STEP 3: RO/RN INVESTIGATION")

print('\n── business_type_mapping for "Renewal / Rollover" ──')
rorn = q("""
    SELECT * FROM business_type_mapping
    WHERE UPPER(TRIM(ui_display_value)) = 'RENEWAL / ROLLOVER'
       OR UPPER(TRIM(source_rule_value)) LIKE '%RO%'
       OR UPPER(TRIM(ui_display_value)) LIKE '%RENEW%'
       OR UPPER(TRIM(ui_display_value)) LIKE '%ROLLOVER%'
       OR UPPER(TRIM(business_type_code)) LIKE '%RO%'
""")
print(f"  Found {len(rorn)} rows:")
for r in rorn:
    print(f"    {dict(r)}")

print('\n── rule_master: Total BT_RO_RN rows ──')
ro_cnt = q("SELECT COUNT(*) as c FROM rule_master WHERE business_type_code = 'BT_RO_RN'")[0]["c"]
print(f"  Total BT_RO_RN rows: {ro_cnt}")

print('\n── rule_master: GCV + BT_RO_RN (first 15 rows) ──')
gcv_ro = q("""
    SELECT product_code, subproduct_code, business_type_code, rule_business_variant,
           subline_code, state_code, location_code, insurer
    FROM rule_master
    WHERE product_code = 'PROD_GCV'
      AND business_type_code = 'BT_RO_RN'
    LIMIT 15
""")
print(f"  Found {len(gcv_ro)} rows for PROD_GCV + BT_RO_RN:")
for r in gcv_ro:
    print(f"    subprod={r['subproduct_code']} | variant={r['rule_business_variant']} | subline={r['subline_code']} | state={r['state_code']} | loc={r['location_code']} | insurer={r['insurer']}")

print('\n── subproduct_mapping: "4W - 12000 TO 20000 GVW" ──')
sp_map = q("""
    SELECT * FROM subproduct_mapping
    WHERE UPPER(TRIM(original_value)) LIKE '%12000%'
       OR UPPER(TRIM(original_value)) LIKE '%20000%'
""")
for r in sp_map:
    print(f"    {dict(r)}")

sp_mast = q("""
    SELECT * FROM subproduct_master
    WHERE UPPER(TRIM(subproduct_name)) LIKE '%12000%'
""")
for r in sp_mast:
    print(f"    [master] {dict(r)}")

# ════════════════════════════════════════════════════════════
# STEP 4 — BUSINESS TYPE FULL MATRIX
# ════════════════════════════════════════════════════════════
hdr("STEP 4: BUSINESS TYPE FULL COVERAGE MATRIX")

all_bt_ui = q("SELECT DISTINCT ui_display_value, business_type_code, source_rule_value FROM business_type_mapping WHERE is_active = 1 ORDER BY business_type_code, ui_display_value")

bt_results = []
for bt in all_bt_ui:
    ui_val = bt["ui_display_value"]
    bt_code = bt["business_type_code"]
    src_rule = bt["source_rule_value"]

    rm_cnt = q("SELECT COUNT(*) as c FROM rule_master WHERE business_type_code = %s", (bt_code,))[0]["c"]
    rm_variants = q("SELECT DISTINCT rule_business_variant FROM rule_master WHERE business_type_code = %s", (bt_code,))
    variant_list = [r["rule_business_variant"] for r in rm_variants]

    first_prod = q("""
        SELECT rm.product_code, pm.product_name, rm.subproduct_code, sm.subproduct_name
        FROM rule_master rm
        JOIN product_master pm ON pm.product_code = rm.product_code
        JOIN subproduct_master sm ON sm.subproduct_code = rm.subproduct_code
        WHERE rm.business_type_code = %s
        LIMIT 1
    """, (bt_code,))

    api_works = "N/A"
    if first_prod:
        p = first_prod[0]
        test_payload = {
            "product": p["product_name"],
            "subproduct": p["subproduct_name"],
            "business_type": ui_val,
            "subline": None, "state": None, "location": None,
            "vehicle_make": None, "vehicle_model": None,
            "engine_cc": None, "gvw": None, "cpa": None,
            "vehicle_age": None, "coverage": None, "rule_business_variant": None
        }
        res, err = api_post("/calculate-inflow", test_payload)
        if res and res.get("matched"):
            api_works = "PASS"
        elif res:
            api_works = f"FAIL: {str(res.get('error','no match'))[:50]}"
        else:
            api_works = f"ERR: {str(err)[:40]}"

    bt_results.append({
        "ui": ui_val, "code": bt_code, "source_rule": src_rule,
        "variants": variant_list, "rm_rows": rm_cnt, "api": api_works
    })
    print(f"  {ui_val:35} | {bt_code:20} | src={str(src_rule):15} | rm_rows={rm_cnt:5} | {api_works}")

# ════════════════════════════════════════════════════════════
# STEP 5 — RULE_MASTER AUTOMATED COVERAGE AUDIT
# ════════════════════════════════════════════════════════════
hdr("STEP 5: RULE_MASTER COVERAGE AUDIT")

grand_total = q("""
    SELECT COUNT(*) as total FROM (
        SELECT DISTINCT product_code, subproduct_code, business_type_code,
                        rule_business_variant, subline_code, state_code, location_code
        FROM rule_master
    ) x
""")[0]["total"]
print(f"  Grand total distinct 7-dim combinations in rule_master: {grand_total}")

sample = q("""
    SELECT DISTINCT
        rm.product_code, pm.product_name,
        rm.subproduct_code, sm.subproduct_name,
        rm.business_type_code, btm.ui_display_value as bt_ui,
        rm.rule_business_variant,
        rm.subline_code, slm.ui_display_value as sl_ui,
        rm.state_code, stm.source_state,
        rm.location_code, lm.source_location
    FROM rule_master rm
    JOIN product_master pm ON pm.product_code = rm.product_code
    JOIN subproduct_master sm ON sm.subproduct_code = rm.subproduct_code
    LEFT JOIN business_type_master btm ON btm.business_type_code = rm.business_type_code
    LEFT JOIN subline_master slm ON slm.subline_code = rm.subline_code
    LEFT JOIN state_master stm ON stm.state_code = rm.state_code
    LEFT JOIN location_master lm ON lm.location_code = rm.location_code
    ORDER BY rm.product_code, rm.business_type_code, rm.state_code
    LIMIT 100
""")

print(f"\nTesting {len(sample)} representative combinations via API...")
passed = 0
failed = 0
fail_list = []

for i, row in enumerate(sample):
    bt_ui = row.get("bt_ui") or row["business_type_code"]
    sl_ui = row.get("sl_ui") or row["subline_code"]
    raw_state = row.get("source_state") or row["state_code"]
    raw_loc = row.get("source_location") or row["location_code"]

    if raw_loc and ("_ALL" in str(raw_loc) or raw_loc == "ALL"):
        continue

    payload = {
        "product": row["product_name"],
        "subproduct": row["subproduct_name"],
        "business_type": bt_ui,
        "subline": sl_ui,
        "state": raw_state,
        "location": raw_loc,
        "vehicle_make": None, "vehicle_model": None,
        "engine_cc": None, "gvw": None, "cpa": None,
        "vehicle_age": None, "coverage": None,
        "rule_business_variant": None
    }

    res, err = api_post("/calculate-inflow", payload)
    if res and res.get("matched"):
        passed += 1
    else:
        failed += 1
        error_detail = ""
        if res:
            error_detail = res.get("error", str(res))
        else:
            error_detail = str(err)
        fail_list.append({
            "product": row["product_name"],
            "subproduct": row["subproduct_name"],
            "business_type": bt_ui,
            "bt_code": row["business_type_code"],
            "variant": row["rule_business_variant"],
            "subline": sl_ui,
            "state": raw_state,
            "location": raw_loc,
            "error": error_detail
        })
        print(f"  FAIL #{failed:03d}: {row['product_name']} | {row['subproduct_name']} | {bt_ui} | {raw_state} | {raw_loc}")
        print(f"         Error: {error_detail[:120]}")

print(f"\n  Coverage Test: {passed} PASS / {failed} FAIL out of {passed+failed} tested")

# ════════════════════════════════════════════════════════════
# STEP 6 — WILDCARD AUDIT
# ════════════════════════════════════════════════════════════
hdr("STEP 6: WILDCARD ARCHITECTURE AUDIT")

wc_locs = q("SELECT DISTINCT location_code, state_code, source_location, location_type FROM location_master WHERE location_code LIKE '%_ALL' OR location_type = 'ALL_STATE' OR source_location = 'ALL'")
print(f"\n  State-wide wildcard locations: {len(wc_locs)}")
for r in wc_locs:
    print(f"    {r['location_code']} | state={r['state_code']} | src={r['source_location']} | type={r['location_type']}")

rm_wc = q("SELECT COUNT(*) as c FROM rule_master WHERE location_code LIKE '%_ALL' OR location_code = 'ALL'")[0]["c"]
print(f"\n  rule_master rows using wildcard location: {rm_wc}")

# ════════════════════════════════════════════════════════════
# STEP 7 — ALL PRODUCTS SUBPRODUCT AUDIT
# ════════════════════════════════════════════════════════════
hdr("STEP 7: ALL PRODUCTS SUBPRODUCT AUDIT")

for prod in prods:
    pcode = prod["product_code"]
    pname = prod["product_name"]
    subprods = q("""
        SELECT sm.subproduct_code, sm.subproduct_name,
               COUNT(DISTINCT rm.insurer) as insurer_count,
               COUNT(DISTINCT rm.business_type_code) as bt_count,
               COUNT(*) as rule_count
        FROM subproduct_master sm
        LEFT JOIN rule_master rm ON rm.subproduct_code = sm.subproduct_code
        WHERE sm.product_code = %s
        GROUP BY sm.subproduct_code, sm.subproduct_name
        ORDER BY sm.subproduct_code
    """, (pcode,))
    print(f"\n  {pcode} | {pname} => {len(subprods)} subproducts:")
    for sp in subprods:
        print(f"    {sp['subproduct_code']:30} | {sp['subproduct_name']:35} | rules={sp['rule_count']} | insurers={sp['insurer_count']} | bt_types={sp['bt_count']}")

# ════════════════════════════════════════════════════════════
# STEP 9 — VARIANT LOGIC AUDIT
# ════════════════════════════════════════════════════════════
hdr("STEP 9: BUSINESS VARIANT DERIVATION LOGIC AUDIT")

print("\n── BT_NEW rule_business_variant values in rule_master ──")
new_variants = q("SELECT DISTINCT product_code, rule_business_variant, COUNT(*) as c FROM rule_master WHERE business_type_code = 'BT_NEW' GROUP BY product_code, rule_business_variant ORDER BY product_code, rule_business_variant")
for r in new_variants:
    print(f"  product={r['product_code']} | variant='{r['rule_business_variant']}' | rows={r['c']}")

print("\n── BT_RO_RN rule_business_variant values in rule_master ──")
ro_variants = q("SELECT DISTINCT rule_business_variant, COUNT(*) as c FROM rule_master WHERE business_type_code = 'BT_RO_RN' GROUP BY rule_business_variant")
for r in ro_variants:
    print(f"  variant='{r['rule_business_variant']}' | rows={r['c']}")

# ════════════════════════════════════════════════════════════
# STEP 10 — DEEP TRACE
# ════════════════════════════════════════════════════════════
hdr("STEP 10: DEEP TRACE - GCV + 4W-12000-20000 + RO/RN + PKG + AP + VIJAYAWADA")

prod_row = q("SELECT product_code FROM product_master WHERE UPPER(product_name) LIKE '%GOODS CARRYING%'")
prod_code = prod_row[0]["product_code"] if prod_row else None
print(f"\n  product_code for 'Goods Carrying Vehicle': {prod_code}")

sp_row = q("SELECT subproduct_code, subproduct_name FROM subproduct_master WHERE UPPER(subproduct_name) LIKE '%12000%' AND product_code = %s", (prod_code,))
sp_code = sp_row[0]["subproduct_code"] if sp_row else None
sp_name = sp_row[0]["subproduct_name"] if sp_row else None
print(f"  subproduct_code for '4W - 12000 TO 20000 GVW': {sp_code} ({sp_name})")

bt_row = q("SELECT business_type_code, source_rule_value FROM business_type_mapping WHERE UPPER(TRIM(ui_display_value)) = UPPER('Renewal / Rollover') LIMIT 1")
bt_code_found = bt_row[0]["business_type_code"] if bt_row else None
bt_src = bt_row[0]["source_rule_value"] if bt_row else None
print(f"  business_type_code for 'Renewal / Rollover': {bt_code_found}")
print(f"  source_rule_value: {bt_src}")

if bt_code_found == "BT_RO_RN":
    derived_variant = "RO/RN"
elif bt_code_found == "BT_NEW":
    derived_variant = "NEW(1+5)" if prod_code == "PROD_2W" else "NEW(1+3)"
else:
    derived_variant = bt_src
print(f"  Derived rule_business_variant: {derived_variant}")

sl_row = q("SELECT subline_code FROM subline_master WHERE UPPER(source_subline) LIKE '%PKG%' OR UPPER(ui_display_value) LIKE '%PACKAGE%' LIMIT 1")
sl_code = sl_row[0]["subline_code"] if sl_row else None
print(f"  subline_code for 'Package': {sl_code}")

st_row = q("SELECT state_code FROM state_master WHERE UPPER(source_state) LIKE '%ANDHRA%' OR UPPER(source_state) LIKE '%ANDHARA%' LIMIT 1")
st_code = st_row[0]["state_code"] if st_row else None
print(f"  state_code for 'ANDHRA PRADESH': {st_code}")

loc_row = q("SELECT location_code, state_code FROM location_master WHERE UPPER(source_location) LIKE '%VIJAYAWADA%' LIMIT 1")
loc_code = loc_row[0]["location_code"] if loc_row else None
loc_state = loc_row[0]["state_code"] if loc_row else None
print(f"  location_code for 'VIJAYAWADA': {loc_code} (state={loc_state})")

exact_match = q("""
    SELECT insurer, inflow FROM rule_master
    WHERE product_code = %(prod)s
      AND subproduct_code = %(sp)s
      AND business_type_code = %(bt)s
      AND rule_business_variant = %(rv)s
      AND subline_code = %(sl)s
      AND state_code = %(st)s
      AND location_code = %(lc)s
""", {
    "prod": prod_code, "sp": sp_code, "bt": bt_code_found,
    "rv": derived_variant, "sl": sl_code, "st": st_code, "lc": loc_code
})
print(f"\n  Exact 7-dim match: {len(exact_match)} rows")
for r in exact_match:
    print(f"    insurer={r['insurer']} | inflow={str(r['inflow'])[:80]}...")

no_loc_match = q("""
    SELECT insurer, inflow, location_code FROM rule_master
    WHERE product_code = %(prod)s
      AND subproduct_code = %(sp)s
      AND business_type_code = %(bt)s
      AND rule_business_variant = %(rv)s
      AND subline_code = %(sl)s
      AND state_code = %(st)s
""", {
    "prod": prod_code, "sp": sp_code, "bt": bt_code_found,
    "rv": derived_variant, "sl": sl_code, "st": st_code
})
print(f"\n  Without location filter: {len(no_loc_match)} rows")
for r in no_loc_match:
    print(f"    insurer={r['insurer']} | loc={r['location_code']}")

no_state_match = q("""
    SELECT insurer, location_code, state_code FROM rule_master
    WHERE product_code = %(prod)s
      AND subproduct_code = %(sp)s
      AND business_type_code = %(bt)s
      AND rule_business_variant = %(rv)s
      AND subline_code = %(sl)s
""", {
    "prod": prod_code, "sp": sp_code, "bt": bt_code_found,
    "rv": derived_variant, "sl": sl_code
})
print(f"\n  Without state/location filter: {len(no_state_match)} rows")
for r in no_state_match[:10]:
    print(f"    insurer={r['insurer']} | state={r['state_code']} | loc={r['location_code']}")

# ════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════
hdr("AUDIT SUMMARY")

print(f"  Business type mapping entries: {len(btm)}")
print(f"  Business type master entries: {len(bts)}")
print(f"  rule_master total rows: {q('SELECT COUNT(*) as c FROM rule_master')[0]['c']}")
print(f"  Grand total distinct 7-dim combinations: {grand_total}")
print(f"\n  Coverage Test: {passed} PASS / {failed} FAIL out of {passed+failed} tested")

if fail_list:
    print(f"\n  FAILURES ({len(fail_list)}):")
    for i, f in enumerate(fail_list, 1):
        print(f"\n  FAIL #{i:03d}:")
        for k, v in f.items():
            print(f"    {k}: {v}")
else:
    print("\n  No failures detected in sample set.")

print("\n  Audit complete.")
cur.close()
conn.close()
