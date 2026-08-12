"""Investigate GCV NEW failure and prepare comprehensive fix."""
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

# Why does GCV + 12000-20000 + New fail with "No matching rule found"?
print("=== GCV + NEW investigation ===")
# Check what variant is derived for GCV + New
# rule_service.py logic: BT_NEW + PROD_GCV => std_variant = 'NEW(1+3)'
print("std_variant for GCV + New => 'NEW(1+3)' (from code logic: non-2W uses NEW(1+3))")

# Check what variants actually exist for GCV + NEW in rule_master
for r in q("SELECT DISTINCT rule_business_variant, COUNT(*) as c FROM rule_master WHERE product_code='PROD_GCV' AND business_type_code='BT_NEW' GROUP BY rule_business_variant"):
    print(f"  GCV+BT_NEW variant in rule_master: '{r['rule_business_variant']}' => {r['c']} rows")

# Is there any GCV + NEW in rule_master at all?
for r in q("SELECT DISTINCT subproduct_code, rule_business_variant, COUNT(*) as c FROM rule_master WHERE product_code='PROD_GCV' AND business_type_code='BT_NEW' GROUP BY subproduct_code, rule_business_variant"):
    print(f"  subprod={r['subproduct_code']} variant='{r['rule_business_variant']}' rows={r['c']}")

# Check for SP_GCV_4W_12000_TO_20000_GVW specifically
for r in q("SELECT DISTINCT business_type_code, rule_business_variant, state_code, COUNT(*) as c FROM rule_master WHERE subproduct_code='SP_GCV_4W_12000_TO_20000_GVW' GROUP BY business_type_code, rule_business_variant, state_code ORDER BY business_type_code, state_code"):
    print(f"  BT={r['business_type_code']} variant='{r['rule_business_variant']}' state={r['state_code']} rows={r['c']}")

print("\n=== 2W + NEW variants in rule_master ===")
for r in q("SELECT DISTINCT rule_business_variant, COUNT(*) as c FROM rule_master WHERE product_code='PROD_2W' AND business_type_code='BT_NEW' GROUP BY rule_business_variant"):
    print(f"  variant='{r['rule_business_variant']}' rows={r['c']}")

print("\n=== PC + NEW variants in rule_master ===")
for r in q("SELECT DISTINCT rule_business_variant, COUNT(*) as c FROM rule_master WHERE product_code='PROD_PC' AND business_type_code='BT_NEW' GROUP BY rule_business_variant"):
    print(f"  variant='{r['rule_business_variant']}' rows={r['c']}")

print("\n=== PCV + NEW variants in rule_master ===")
for r in q("SELECT DISTINCT rule_business_variant, COUNT(*) as c FROM rule_master WHERE product_code='PROD_PCV' AND business_type_code='BT_NEW' GROUP BY rule_business_variant"):
    print(f"  variant='{r['rule_business_variant']}' rows={r['c']}")

print("\n=== MISC + NEW variants in rule_master ===")
for r in q("SELECT DISTINCT rule_business_variant, COUNT(*) as c FROM rule_master WHERE product_code='PROD_MISC' AND business_type_code='BT_NEW' GROUP BY rule_business_variant"):
    print(f"  variant='{r['rule_business_variant']}' rows={r['c']}")

# Summary of all NEW variants by product
print("\n=== ALL products: BT_NEW variants in rule_master ===")
for r in q("SELECT product_code, rule_business_variant, COUNT(*) as c FROM rule_master WHERE business_type_code='BT_NEW' GROUP BY product_code, rule_business_variant ORDER BY product_code, rule_business_variant"):
    print(f"  product={r['product_code']} variant='{r['rule_business_variant']}' rows={r['c']}")

print("\n=== CONCLUSION ===")
print("If GCV does NOT appear in BT_NEW rule_master rows, there are NO GCV New rules in the database.")
print("That is not a bug in the code — it means GCV simply has no 'New' business rules in source data.")

# Verify: what is the total NEW row count vs RO/RN
new_total = q("SELECT COUNT(*) as c FROM rule_master WHERE business_type_code='BT_NEW'")[0]['c']
rorn_total = q("SELECT COUNT(*) as c FROM rule_master WHERE business_type_code='BT_RO_RN'")[0]['c']
print(f"\nrule_master BT_NEW rows: {new_total}")
print(f"rule_master BT_RO_RN rows: {rorn_total}")

print("\n=== state_mapping for AP ===")
for r in q("SELECT * FROM state_mapping WHERE state_code='ST_AP'"):
    print(dict(r))

cur.close()
conn.close()
print("\nDone.")
