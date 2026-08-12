"""Full coverage audit — tests every distinct product+bt combo."""
import json, urllib.request, pymysql, os
from dotenv import load_dotenv
load_dotenv()
conn = pymysql.connect(
    host=os.getenv('DB_HOST','localhost'),
    port=int(os.getenv('DB_PORT',3306)),
    user=os.getenv('DB_USER','root'),
    password=os.getenv('DB_PASSWORD',''),
    database=os.getenv('DB_NAME','inflow_db'),
    charset='utf8mb4'
)
cur = conn.cursor(pymysql.cursors.DictCursor)

def q(sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()

def api_post(endpoint, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8001" + endpoint, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as ex:
        return None, str(ex)

# Load what the /business-types endpoint returns (what frontend shows)
bt_master = q("SELECT business_type_code, ui_display_value FROM business_type_master ORDER BY business_type_code")
print("Business types shown in frontend dropdown:")
for bt in bt_master:
    print(f"  {bt['business_type_code']} => '{bt['ui_display_value']}'")

# Test each product + subproduct + business_type combo with no other filters
print("\n=== COVERAGE AUDIT: Product + SubProduct + BusinessType only ===")
sample = q("""
    SELECT DISTINCT
        rm.product_code, pm.product_name,
        rm.subproduct_code, sm.subproduct_name,
        rm.business_type_code
    FROM rule_master rm
    JOIN product_master pm ON pm.product_code = rm.product_code
    JOIN subproduct_master sm ON sm.subproduct_code = rm.subproduct_code
    ORDER BY rm.product_code, rm.business_type_code, rm.subproduct_code
""")
print(f"Total distinct (product, subproduct, bt) combos: {len(sample)}")

passed = failed = 0
fail_list = []

for row in sample:
    # Get the UI display value that the frontend would use for this bt_code
    bt_ui_rows = [x for x in bt_master if x['business_type_code'] == row['business_type_code']]
    bt_ui = bt_ui_rows[0]['ui_display_value'] if bt_ui_rows else row['business_type_code']

    payload = {
        "product": row["product_name"],
        "subproduct": row["subproduct_name"],
        "business_type": bt_ui,
        "subline": None, "state": None, "location": None,
        "vehicle_make": None, "vehicle_model": None,
        "engine_cc": None, "gvw": None, "cpa": None,
        "vehicle_age": None, "coverage": None, "rule_business_variant": None
    }
    res, err = api_post("/calculate-inflow", payload)
    if res and res.get("matched"):
        passed += 1
    else:
        failed += 1
        error_detail = res.get("error", str(res)) if res else str(err)
        fail_list.append({
            "product": row["product_name"],
            "subproduct": row["subproduct_name"],
            "bt_code": row["business_type_code"],
            "bt_ui": bt_ui,
            "error": error_detail
        })

print(f"\nResult: {passed} PASS / {failed} FAIL out of {passed+failed}")
if fail_list:
    print(f"\nFAILURES ({len(fail_list)}):")
    for i, f in enumerate(fail_list, 1):
        print(f"  #{i:03d}: {f['product']} | {f['subproduct']} | bt_ui='{f['bt_ui']}' | {f['error'][:80]}")

# Also test with state+location for the reported broken case
print("\n=== SPECIFIC BROKEN CASE TEST ===")
test_cases = [
    ("Goods Carrying Vehicle", "4W - 12000 TO 20000 GVW", "New", "Package", "ANDHARA PRADESH", "VIJAYAWADA"),
    ("Goods Carrying Vehicle", "4W - 12000 TO 20000 GVW", "Renewal / Rollover", "Package", "ANDHARA PRADESH", "VIJAYAWADA"),
    ("Two Wheeler", "Scooter", "New", "Package", "TAMIL NADU", "CHENNAI"),
    ("Two Wheeler", "Scooter", "Renewal / Rollover", "Package", "TAMIL NADU", "CHENNAI"),
    ("Private Car", "Private Car", "New", "Package", "KARNATAKA", None),
    ("Private Car", "Private Car", "Renewal / Rollover", "Package", "KARNATAKA", None),
]
for prod, sp, bt, sl, st, loc in test_cases:
    payload = {
        "product": prod, "subproduct": sp, "business_type": bt,
        "subline": sl, "state": st, "location": loc,
        "vehicle_make": None, "vehicle_model": None,
        "engine_cc": None, "gvw": None, "cpa": None,
        "vehicle_age": None, "coverage": None, "rule_business_variant": None
    }
    res, err = api_post("/calculate-inflow", payload)
    if res and res.get("matched"):
        insurers = [x["insurer"] for x in res.get("results", [])]
        print(f"  PASS: {prod[:20]} | {sp[:30]} | {bt} => {len(insurers)} insurers: {', '.join(insurers[:5])}")
    else:
        error = res.get("error", str(err)) if res else str(err)
        print(f"  FAIL: {prod[:20]} | {sp[:30]} | {bt} => {error[:80]}")

cur.close()
conn.close()
print("\nAudit done.")
