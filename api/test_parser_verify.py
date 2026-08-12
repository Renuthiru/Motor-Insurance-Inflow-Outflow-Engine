"""Parser verification against ALL real DB expressions + end-to-end API tests."""
import sys, json, urllib.request
sys.path.append(r"D:\Inflow\api")
from database import engine
from sqlalchemy import text
from services.inflow_parser import InflowParser

PASS, FAIL = "PASS", "FAIL"
BASE_URL = "http://127.0.0.1:8001"

def post(ep, d):
    try:
        b = json.dumps(d).encode()
        r = urllib.request.Request(BASE_URL+ep, data=b, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(r, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"matched":False,"error":e.read().decode(),"results":[]}
    except Exception as e:
        return {"matched":False,"error":str(e),"results":[]}

def get(ep):
    try:
        with urllib.request.urlopen(BASE_URL+ep, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"__ex__":str(e)}

results = []
def L(n, desc, ok, detail=""):
    s = PASS if ok else FAIL
    results.append((s, n, desc))
    print("TEST %02d [%s] %s" % (n, s, desc))
    if detail:
        print("         " + str(detail)[:130])

print("=" * 65)
print("  PHASE 1: PARSER UNIT TESTS vs REAL DB EXPRESSIONS")
print("=" * 65)

# ---- T1: -2% NOT treated as a rate ----
e = "40.00%{NT(W/O CPA -2% Less - SUZUKI - Upto 150cc),38.50%{NT(W/O CPA -2% Less - Hero - Upto 150cc)"
segs = InflowParser.parse_expression(e)
rates = [s["rate"] for s in segs]
L(1, "-2% inside condition not treated as rate",
  2.0 not in rates and 40.0 in rates and 38.5 in rates,
  "rates=%s" % rates)

# ---- T2: Upto CC ----
upto_seg = next((s for s in segs if s["cc_max"] == 150), None)
L(2, "Upto 150cc parsed correctly (cc_min=0, cc_max=150)",
  upto_seg is not None and upto_seg["cc_min"] == 0 and upto_seg["cc_max"] == 150,
  str(upto_seg))

# ---- T3: CC range (>150cc-350cc) ----
e2 = "40.00%{NT(W/O CPA -2% Less - SUZUKI - >150cc-350cc)"
s2 = InflowParser.parse_expression(e2)
range_seg = s2[0] if s2 else None
L(3, "CC range >150cc-350cc (cc_min=150, cc_max=350)",
  range_seg and range_seg["cc_min"] == 150 and range_seg["cc_max"] == 350,
  str(range_seg))

# ---- T4: Above CC ----
e3 = "20.00%{NT(W/O CPA -2% Less - Above 1500CC)"
s3 = InflowParser.parse_expression(e3)
above_seg = s3[0] if s3 else None
L(4, "Above 1500CC (cc_min=1500, cc_max=999999)",
  above_seg and above_seg["cc_min"] == 1500 and above_seg["cc_max"] == 999999,
  str(above_seg))

# ---- T5: Multiple CC segments with multiple makes ----
e4 = "40.00%{NT(W/O CPA -2% Less - SUZUKI - Upto 150cc),40.00%{NT(W/O CPA -2% Less - SUZUKI - >150cc-350cc),38.50%{NT(W/O CPA -2% Less - Hero - Upto 150cc),38.50%{NT(W/O CPA -2% Less - Hero - >150cc-350cc),31.00%{NT(W/O CPA -2% Less - Yamaha - Upto 150cc)"
s4 = InflowParser.parse_expression(e4)
L(5, "5 multi-make segments parsed (count=5)",
  len(s4) == 5, "count=%d rates=%s" % (len(s4), [s["rate"] for s in s4]))

# ---- T6: CPA=False detection ----
L(6, "CPA=False correctly set on W/O CPA segment",
  all(s["cpa"] == False for s in s4), "cpas=%s" % [s["cpa"] for s in s4])

# ---- T7: Make detection ----
suzuki_seg = next((s for s in s4 if "SUZUKI" in s["allowed_makes"]), None)
L(7, "SUZUKI make detected in allowed_makes",
  suzuki_seg is not None, str(suzuki_seg["allowed_makes"] if suzuki_seg else None))

# ---- T8: NT coverage ----
L(8, "Coverage=NT correctly detected",
  all(s["coverage"] == "NT" for s in s4),
  "coverages=%s" % [s["coverage"] for s in s4])

# ---- T9: GVW Ton parsing ----
e5 = "22.00%{NT(W/O CPA -2% Less - Upto 16K Ton),17.00%{NT(W/O CPA -2% Less - Aove 16K Ton)"
s5 = InflowParser.parse_expression(e5)
gvw_seg = s5[0] if s5 else None
L(9, "GVW Upto 16K Ton parsed (gvw_max=16000)",
  gvw_seg and gvw_seg["gvw_max"] == 16000,
  "gvw_min=%s gvw_max=%s" % (gvw_seg["gvw_min"] if gvw_seg else None, gvw_seg["gvw_max"] if gvw_seg else None))

# ---- T10: Flat rate (no conditions) ----
e6 = "29.50%{NT(W/O CPA -2% Less)"
s6 = InflowParser.parse_expression(e6)
L(10, "Flat rate 29.50% with CPA=False (no CC/make)",
  len(s6) == 1 and s6[0]["rate"] == 29.5 and s6[0]["cpa"] == False
  and s6[0]["cc_max"] is None and s6[0]["allowed_makes"] == [],
  str(s6[0] if s6 else None))

# ---- T11: NT + OD split ----
e7 = "47.50%{NT,19.50%{OD"
s7 = InflowParser.parse_expression(e7)
nt_seg = next((s for s in s7 if s["coverage"] == "NT"), None)
od_seg = next((s for s in s7 if s["coverage"] == "OD"), None)
L(11, "NT + OD split parsed correctly",
  nt_seg and nt_seg["rate"] == 47.5 and od_seg and od_seg["rate"] == 19.5,
  "NT=%.1f OD=%.1f" % (nt_seg["rate"] if nt_seg else 0, od_seg["rate"] if od_seg else 0))

# ---- T12: Except model ----
e8 = "55.00%{NT(Except Bolero),19.50%{OD(Except Bolero)"
s8 = InflowParser.parse_expression(e8)
exc_seg = s8[0] if s8 else None
L(12, "Except Bolero parsed (exclude_models=[BOLERO])",
  exc_seg and "BOLERO" in exc_seg.get("exclude_models", []),
  str(exc_seg["exclude_models"] if exc_seg else None))

# ---- T13: Vehicle age parsing ----
e9 = "49.50%{NT(<=5Yr - TATA Upto 3.0Ton),49.50%{NT(>5Yr - TATA Upto 3.0Ton)"
s9 = InflowParser.parse_expression(e9)
young_seg = next((s for s in s9 if s["age_max"] == 5), None)
old_seg = next((s for s in s9 if s.get("age_min") == 5), None)
L(13, "Vehicle age <=5yr and >5yr parsed",
  young_seg is not None and old_seg is not None,
  "young_age=%s old_age_min=%s" % (young_seg, old_seg))

# ---- T14: Petrol fuel type ----
e10 = "20.00%{OD(Above 1500CC - petrol)"
s10 = InflowParser.parse_expression(e10)
fuel_seg = s10[0] if s10 else None
L(14, "Petrol fuel type detected",
  fuel_seg and fuel_seg.get("fuel_type") == "PETROL",
  "fuel=%s" % (fuel_seg["fuel_type"] if fuel_seg else None))

# ---- T15: Parse all 1974 distinct expressions without crash ----
print("\n--- Parsing all distinct DB expressions ---")
with engine.connect() as conn:
    rows = conn.execute(text("SELECT DISTINCT inflow FROM rule_master")).fetchall()
errors = []
for r in rows:
    try:
        InflowParser.parse_expression(r[0])
    except Exception as ex:
        errors.append((r[0][:60], str(ex)))
L(15, "All %d distinct DB expressions parse without crash" % len(rows),
  len(errors) == 0,
  "errors=%d first=%s" % (len(errors), errors[:1] if errors else "none"))

print("\n" + "=" * 65)
print("  PHASE 2: END-TO-END /calculate-inflow API TESTS")
print("=" * 65)

BASE = {
    "product": "Two Wheeler", "subproduct": "Bike",
    "business_type": "New", "subline": "Package",
    "state": "ANDHARA PRADESH", "location": "VIJAYAWADA",
    "vehicle_make": "SUZUKI", "engine_cc": 125, "cpa": False
}

# ---- T16: Valid CC + Make match ----
r16 = post("/calculate-inflow", BASE)
rt16 = r16.get("results",[{}])[0].get("rate") if r16.get("matched") else None
L(16, "E2E: SUZUKI 125cc => 40.0% (Vijayawada AP)",
  r16.get("matched") and rt16 == 40.0,
  "matched=%s rate=%s err=%s" % (r16.get("matched"), rt16, r16.get("error")))

# ---- T17: CC upper-bound ----
r17 = post("/calculate-inflow", dict(BASE, engine_cc=150))
rt17 = r17.get("results",[{}])[0].get("rate") if r17.get("matched") else None
L(17, "E2E: SUZUKI 150cc => 40.0% (upper bound Upto 150cc)",
  r17.get("matched") and rt17 == 40.0, "rate=%s" % rt17)

# ---- T18: CC range segment ----
r18 = post("/calculate-inflow", dict(BASE, engine_cc=220))
rt18 = r18.get("results",[{}])[0].get("rate") if r18.get("matched") else None
rule18 = r18.get("results",[{}])[0].get("matched_rule","")[:70]
L(18, "E2E: SUZUKI 220cc => >150cc-350cc segment => 40.0%",
  r18.get("matched") and rt18 == 40.0,
  "rate=%s rule=%s" % (rt18, rule18))

# ---- T19: Different make ----
r19 = post("/calculate-inflow", dict(BASE, vehicle_make="HERO"))
rt19 = r19.get("results",[{}])[0].get("rate") if r19.get("matched") else None
L(19, "E2E: HERO 125cc => 38.5%",
  r19.get("matched") and rt19 == 38.5, "rate=%s" % rt19)

# ---- T20: Unknown make => no match ----
r20 = post("/calculate-inflow", dict(BASE, vehicle_make="HARLEY_XYZ999"))
L(20, "E2E: Unknown make => no match",
  not r20.get("matched"), "matched=%s err=%s" % (r20.get("matched"), r20.get("error")))

# ---- T21: CPA=False => matches W/O CPA ----
r21 = post("/calculate-inflow", dict(BASE, cpa=False))
L(21, "E2E: cpa=False => matches W/O CPA rules",
  r21.get("matched") and r21.get("results",[{}])[0].get("rate") is not None,
  "rate=%s" % r21.get("results",[{}])[0].get("rate"))

# ---- T22: CPA=True => no match (all rules are W/O CPA) ----
r22 = post("/calculate-inflow", dict(BASE, cpa=True))
L(22, "E2E: cpa=True => no match (rules are W/O CPA only)",
  not r22.get("matched"),
  "matched=%s err=%s" % (r22.get("matched"), r22.get("error")))

# ---- T23: Impossible CC => no match ----
r23 = post("/calculate-inflow", dict(BASE, engine_cc=999999))
L(23, "E2E: CC=999999 => no segment match",
  not r23.get("matched"), "err=%s" % r23.get("error"))

# ---- T24: State-wide wildcard UK+ALL ----
r24 = post("/calculate-inflow", {
    "product":"Two Wheeler","subproduct":"Bike","business_type":"New",
    "subline":"Package","state":"UTTARKHAND","location":"ALL",
    "vehicle_make":"SUZUKI","engine_cc":125,"cpa":False
})
L(24, "E2E: UTTARKHAND+ALL => LOC_UK_ALL wildcard",
  r24.get("matched") and len(r24.get("results",[])) >= 1,
  "count=%d err=%s" % (len(r24.get("results",[])), r24.get("error")))

# ---- T25: GOA wildcard ----
r25 = post("/calculate-inflow", {
    "product":"Two Wheeler","subproduct":"Bike","business_type":"New",
    "subline":"Package","state":"GOA","location":"ALL",
    "vehicle_make":"SUZUKI","engine_cc":125,"cpa":False
})
L(25, "E2E: GOA+ALL => LOC_GA_ALL wildcard",
  r25.get("matched"), "count=%d err=%s" % (len(r25.get("results",[])), r25.get("error")))

# ---- T26: Invalid product ----
r26 = post("/calculate-inflow", dict(BASE, product="INVALID XYZ"))
L(26, "E2E: Invalid product => clear error",
  not r26.get("matched") and "Product mapping not found" in str(r26.get("error","")),
  "err=%s" % r26.get("error"))

# ---- T27: Invalid state ----
r27 = post("/calculate-inflow", dict(BASE, state="FAKE STATE 999"))
L(27, "E2E: Invalid state => clear error",
  not r27.get("matched") and "State mapping not found" in str(r27.get("error","")),
  "err=%s" % r27.get("error"))

# ---- T28: Invalid location ----
r28 = post("/calculate-inflow", dict(BASE, location="NONEXISTENT"))
L(28, "E2E: Invalid location => clear error",
  not r28.get("matched") and "Location mapping not found" in str(r28.get("error","")),
  "err=%s" % r28.get("error"))

# ---- T29: DB vs API direct comparison ----
print("\n--- T29: Direct DB vs API inflow-lookup comparison ---")
sql = ("SELECT insurer,inflow FROM rule_master WHERE "
       "product_code='PROD_2W' AND subproduct_code='SP_2W_BIKE' AND "
       "business_type_code='BT_NEW' AND rule_business_variant='NEW(1+5)' AND "
       "subline_code='SL_PKG' AND state_code='ST_AP' AND location_code='LOC_AP_VIJAYAWADA'")
with engine.connect() as conn:
    dbrows = conn.execute(text(sql)).fetchall()
apir = post("/inflow-lookup", {
    "product":"Two Wheeler","subproduct":"Bike","business_type":"New",
    "subline":"Package","state":"ANDHARA PRADESH","location":"VIJAYAWADA"
})
dbi = sorted([r.insurer for r in dbrows])
apii = sorted([r["insurer"] for r in apir.get("results",[])])
dbin = set(r.inflow for r in dbrows)
apiin = set(r["inflow"] for r in apir.get("results",[]))
print("  DB  insurers: %s" % dbi)
print("  API insurers: %s" % apii)
print("  Inflow match: %s" % (dbin == apiin))
L(29, "DB vs API exact inflow match", dbi == apii and dbin == apiin)

# ---- T30: All existing endpoints still work ----
eps = ["/","/health","/products","/subproducts","/business-types",
       "/states","/locations","/sublines","/product-mappings",
       "/state-mappings","/location-mappings"]
all_ok = True
for ep in eps:
    resp = get(ep)
    if "__ex__" in resp:
        all_ok = False
        print("  FAIL ep=%s: %s" % (ep, resp))
L(30, "All existing 11 GET endpoints still working", all_ok)

# ---- T31: /rule-lookup still works ----
rl = post("/rule-lookup", {
    "product_code":"PROD_2W","subproduct_code":"SP_2W_BIKE",
    "business_type_code":"BT_NEW","rule_business_variant":"NEW(1+5)",
    "subline_code":"SL_PKG","state_code":"ST_AP","location_code":"LOC_AP_VIJAYAWADA"
})
L(31, "/rule-lookup still works", rl.get("matched") and rl.get("count",0) > 0,
  "count=%s" % rl.get("count"))

# SUMMARY
print("\n" + "=" * 65)
p = sum(1 for s,_,_ in results if s == PASS)
f = sum(1 for s,_,_ in results if s == FAIL)
print("  RESULTS: %d/%d PASSED | %d FAILED" % (p, len(results), f))
print("=" * 65)
if f:
    print("  FAILED:")
    for s,n,d in results:
        if s == FAIL:
            print("    TEST %02d: %s" % (n, d))
