import urllib.request
import json
import sys
sys.path.append(r"D:\Inflow\api")
from database import engine
from sqlalchemy import text

BASE_URL = "http://127.0.0.1:8001"
PASS, FAIL = "PASS", "FAIL"
log_results = []

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

def L(n, desc, ok, detail=""):
    s = PASS if ok else FAIL
    log_results.append((s, n, desc))
    print("TEST %02d [%s] %s" % (n, s, desc))
    if detail:
        print("         " + str(detail)[:120])

print("=" * 60)
print("  INFLOW CALCULATION ENGINE -- COMPLETE TEST SUITE")
print("=" * 60)

BASE = {
    "product": "Two Wheeler",
    "subproduct": "Bike",
    "business_type": "New",
    "subline": "Package",
    "state": "ANDHARA PRADESH",
    "location": "VIJAYAWADA",
    "vehicle_make": "SUZUKI",
    "engine_cc": 125,
    "cpa": False
}

r1 = post("/calculate-inflow", BASE)
rt1 = r1.get("results",[{}])[0].get("rate") if r1.get("matched") else None
L(1, "Valid CC match SUZUKI 125cc => 40.0%", r1.get("matched") and rt1 == 40.0,
  "matched=%s rate=%s err=%s" % (r1.get("matched"), rt1, r1.get("error")))

r2 = post("/calculate-inflow", dict(BASE, engine_cc=150))
rt2 = r2.get("results",[{}])[0].get("rate") if r2.get("matched") else None
L(2, "CC upper-bound SUZUKI 150cc => 40.0%", r2.get("matched") and rt2 == 40.0, "rate=%s" % rt2)

r3 = post("/calculate-inflow", dict(BASE, engine_cc=220))
rt3 = r3.get("results",[{}])[0].get("rate") if r3.get("matched") else None
rule3 = r3.get("results",[{}])[0].get("matched_rule","")[:60]
L(3, "CC range SUZUKI 220cc => 40.0%", r3.get("matched") and rt3 == 40.0,
  "rate=%s rule=%s" % (rt3, rule3))

r4 = post("/calculate-inflow", dict(BASE, vehicle_make="HERO"))
rt4 = r4.get("results",[{}])[0].get("rate") if r4.get("matched") else None
L(4, "Make HERO 125cc => 38.5%", r4.get("matched") and rt4 == 38.5, "rate=%s" % rt4)

r5 = post("/calculate-inflow", dict(BASE, vehicle_make="HARLEY_XYZ999"))
L(5, "Unknown make => no match", not r5.get("matched"),
  "matched=%s err=%s" % (r5.get("matched"), r5.get("error")))

r6 = post("/calculate-inflow", dict(BASE, cpa=False))
L(6, "CPA=False matches W/O CPA rules",
  r6.get("matched") and r6.get("results",[{}])[0].get("rate") is not None)

r7 = post("/calculate-inflow", dict(BASE, cpa=True))
L(7, "CPA=True => W/O CPA rules do not match", not r7.get("matched"),
  "matched=%s err=%s" % (r7.get("matched"), r7.get("error")))

r8 = post("/calculate-inflow", dict(BASE, engine_cc=999999))
L(8, "Impossible CC 999999cc => no match", not r8.get("matched"),
  "err=%s" % r8.get("error"))

r9 = post("/calculate-inflow", {
    "product": "Two Wheeler", "subproduct": "Bike",
    "business_type": "New", "subline": "Package",
    "state": "UTTARKHAND", "location": "ALL",
    "vehicle_make": "SUZUKI", "engine_cc": 125, "cpa": False
})
L(9, "UTTARKHAND+ALL => LOC_UK_ALL wildcard multi-insurer",
  r9.get("matched") and len(r9.get("results",[])) >= 1,
  "count=%s err=%s std=%s" % (len(r9.get("results",[])), r9.get("error"), r9.get("standardized_input")))

r10 = post("/calculate-inflow", {
    "product": "Two Wheeler", "subproduct": "Bike",
    "business_type": "New", "subline": "Package",
    "state": "GOA", "location": "ALL",
    "vehicle_make": "SUZUKI", "engine_cc": 125, "cpa": False
})
L(10, "GOA+ALL => LOC_GA_ALL state-wide wildcard",
  r10.get("matched") and len(r10.get("results",[])) >= 1,
  "count=%s err=%s" % (len(r10.get("results",[])), r10.get("error")))

r11 = post("/calculate-inflow", {
    "product": "Miscellaneous Vehicle", "subproduct": "Bulldozer",
    "business_type": "Renewal", "subline": "Package",
    "state": "ANDHARA PRADESH", "location": "VIJAYAWADA"
})
L(11, "SP_MISC_ALL Misc Vehicle AP (matched or explained error)",
  r11.get("matched") or r11.get("error") is not None,
  "matched=%s err=%s" % (r11.get("matched"), r11.get("error")))

r12 = post("/calculate-inflow", dict(BASE, product="INVALID VEHICLE XYZ"))
L(12, "Invalid product => clear error",
  not r12.get("matched") and "Product mapping not found" in str(r12.get("error","")),
  "err=%s" % r12.get("error"))

r13 = post("/calculate-inflow", dict(BASE, state="FAKE STATE 999"))
L(13, "Invalid state => clear error",
  not r13.get("matched") and "State mapping not found" in str(r13.get("error","")),
  "err=%s" % r13.get("error"))

r14 = post("/calculate-inflow", dict(BASE, location="NONEXISTENT CITY"))
L(14, "Invalid location => clear error",
  not r14.get("matched") and "Location mapping not found" in str(r14.get("error","")),
  "err=%s" % r14.get("error"))

print("--- TEST 15: Direct DB vs API ---")
sql_q = (
    "SELECT insurer, inflow FROM rule_master "
    "WHERE product_code='PROD_2W' AND subproduct_code='SP_2W_BIKE' "
    "AND business_type_code='BT_NEW' AND rule_business_variant='NEW(1+5)' "
    "AND subline_code='SL_PKG' AND state_code='ST_AP' "
    "AND location_code='LOC_AP_VIJAYAWADA'"
)
with engine.connect() as conn:
    dbrows = conn.execute(text(sql_q)).fetchall()
apir = post("/inflow-lookup", {
    "product": "Two Wheeler", "subproduct": "Bike", "business_type": "New",
    "subline": "Package", "state": "ANDHARA PRADESH", "location": "VIJAYAWADA"
})
dbi = sorted([r.insurer for r in dbrows])
apii = sorted([r["insurer"] for r in apir.get("results",[])])
dbin = set([r.inflow for r in dbrows])
apiin = set([r["inflow"] for r in apir.get("results",[])])
print("DB insurers: %s | API insurers: %s" % (dbi, apii))
print("Inflow match: %s" % (dbin == apiin))
L(15, "DB vs API exact match (/inflow-lookup)", dbi == apii and dbin == apiin)

eps = ["/","/health","/products","/subproducts","/business-types",
       "/states","/locations","/sublines","/product-mappings",
       "/state-mappings","/location-mappings","/subproduct-mappings",
       "/business-type-mappings","/subline-mappings"]
all_ok16 = True
for ep in eps:
    resp = get(ep)
    if "__ex__" in resp:
        all_ok16 = False
        print("  FAIL %s: %s" % (ep, resp))
L(16, "All existing endpoints still responding", all_ok16)

rl = post("/rule-lookup", {
    "product_code": "PROD_2W", "subproduct_code": "SP_2W_BIKE",
    "business_type_code": "BT_NEW", "rule_business_variant": "NEW(1+5)",
    "subline_code": "SL_PKG", "state_code": "ST_AP",
    "location_code": "LOC_AP_VIJAYAWADA"
})
L(17, "/rule-lookup still works", rl.get("matched") and rl.get("count",0) > 0,
  "count=%s" % rl.get("count"))

print("=" * 60)
p = sum(1 for s,_,_ in log_results if s == PASS)
f = sum(1 for s,_,_ in log_results if s == FAIL)
print("RESULTS: %d/%d PASSED | %d FAILED" % (p, len(log_results), f))
print("=" * 60)
if f:
    print("Failed tests:")
    for s,n,d in log_results:
        if s == FAIL:
            print("  FAIL TEST %02d: %s" % (n, d))
