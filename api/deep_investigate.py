"""Deep investigation script for business_type_mapping root cause."""
import pymysql, os
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

print("=== ALL business_type_mapping rows ===")
for r in q("SELECT * FROM business_type_mapping ORDER BY mapping_id"):
    print(dict(r))

print("\n=== Query for 'Renewal / Rollover' ===")
rows = q("""
    SELECT business_type_code, source_rule_value
    FROM business_type_mapping
    WHERE UPPER(TRIM(ui_display_value)) = UPPER('Renewal / Rollover')
       OR UPPER(TRIM(source_rule_value)) = UPPER('Renewal / Rollover')
       OR UPPER(TRIM(business_type_code)) = UPPER('Renewal / Rollover')
""")
print("Rows found:", rows)

print("\n=== All distinct ui_display_value in business_type_mapping ===")
for r in q("SELECT DISTINCT ui_display_value, business_type_code, source_rule_value, is_active FROM business_type_mapping"):
    print(r)

print("\n=== BT_RO_RN variants in rule_master ===")
for r in q("SELECT DISTINCT rule_business_variant, COUNT(*) as c FROM rule_master WHERE business_type_code='BT_RO_RN' GROUP BY rule_business_variant"):
    print(r)

print("\n=== All distinct business_type_code + variant combos in rule_master ===")
for r in q("SELECT DISTINCT business_type_code, rule_business_variant, COUNT(*) as c FROM rule_master GROUP BY business_type_code, rule_business_variant ORDER BY business_type_code, rule_business_variant"):
    print(r)

print("\n=== GCV subproduct codes ===")
for r in q("SELECT subproduct_code, subproduct_name FROM subproduct_master WHERE product_code='PROD_GCV'"):
    print(r)

print("\n=== rule_master PROD_GCV + BT_RO_RN (first 15) ===")
for r in q("SELECT DISTINCT subproduct_code, rule_business_variant, state_code, location_code, insurer FROM rule_master WHERE product_code='PROD_GCV' AND business_type_code='BT_RO_RN' LIMIT 15"):
    print(r)

print("\n=== State master for Andhra Pradesh ===")
for r in q("SELECT state_code, source_state, ui_display_value FROM state_master WHERE UPPER(source_state) LIKE '%ANDHRA%' OR UPPER(source_state) LIKE '%ANDHARA%'"):
    print(r)

print("\n=== Location VIJAYAWADA ===")
for r in q("SELECT location_code, state_code, source_location FROM location_master WHERE UPPER(source_location) LIKE '%VIJAYAWADA%'"):
    print(r)

print("\n=== subline_master ===")
for r in q("SELECT * FROM subline_master"):
    print(r)

print("\n=== What does frontend dropdown show for business types? ===")
print("(from /business-types endpoint, which queries business_type_master)")
for r in q("SELECT business_type_code, canonical_business_type, ui_display_value FROM business_type_master"):
    print(r)

cur.close()
conn.close()
print("\nDone.")
