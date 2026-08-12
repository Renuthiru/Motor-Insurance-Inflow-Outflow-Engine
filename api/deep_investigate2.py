"""Part 2 of deep investigation — no % in SQL strings."""
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

# State master
print("=== State master: Andhra Pradesh ===")
for r in q("SELECT state_code, source_state, ui_display_value FROM state_master WHERE state_code IN ('ST_AP','ST_TN','ST_MH','ST_KA','ST_UK','ST_GA') OR source_state LIKE 'ANDHRA' OR ui_display_value LIKE 'Andhra'"):
    print(r)

print("\n=== ALL state_master entries (for reference) ===")
for r in q("SELECT state_code, source_state, ui_display_value FROM state_master ORDER BY state_code LIMIT 30"):
    print(r)

print("\n=== Location for VIJAYAWADA ===")
for r in q("SELECT location_code, state_code, source_location, ui_display_value FROM location_master WHERE source_location = 'VIJAYAWADA' OR location_code = 'LOC_AP_VIJAYAWADA'"):
    print(r)

print("\n=== subline_master ===")
for r in q("SELECT * FROM subline_master"):
    print(r)

print("\n=== business_type_master UI display values ===")
for r in q("SELECT business_type_code, canonical_business_type, ui_display_value FROM business_type_master"):
    print(r)

# The KEY question: what does the frontend dropdown show?
# The frontend queries /business-types which returns business_type_master.ui_display_value
# business_type_master has "Renewal / Rollover" but business_type_mapping only has "Renewal" and "Rollover"
# This is the mismatch!

print("\n=== DIAGNOSIS: Does business_type_master.ui_display_value match business_type_mapping.ui_display_value? ===")
print("business_type_master entries:")
for r in q("SELECT business_type_code, ui_display_value FROM business_type_master"):
    print(f"  master: code={r['business_type_code']} ui_display={repr(r['ui_display_value'])}")

print("\nbusiness_type_mapping ui_display_value entries:")
for r in q("SELECT DISTINCT business_type_code, ui_display_value FROM business_type_mapping"):
    print(f"  mapping: code={r['business_type_code']} ui_display={repr(r['ui_display_value'])}")

# Test the exact lookup that rule_service.py does
test_val = 'Renewal / Rollover'
print(f"\n=== Simulating rule_service.py bt_sql lookup for '{test_val}' ===")
for r in q("""
    SELECT business_type_code, source_rule_value, applicable_subline_code
    FROM business_type_mapping
    WHERE UPPER(TRIM(ui_display_value)) = UPPER(TRIM('Renewal / Rollover'))
       OR UPPER(TRIM(source_rule_value)) = UPPER(TRIM('Renewal / Rollover'))
       OR UPPER(TRIM(business_type_code)) = UPPER(TRIM('Renewal / Rollover'))
"""):
    print(r)
print("Result: empty = CONFIRMED BUG")

# The fix: business_type_mapping needs an entry with ui_display_value = 'Renewal / Rollover'
# OR: business_type_master.ui_display_value should match what is in business_type_mapping
print("\n=== Fix options ===")
print("Option A (database fix): INSERT INTO business_type_mapping a row with ui_display_value='Renewal / Rollover'")
print("Option B (mapping fix): Change business_type_master.ui_display_value to match 'Renewal' or 'Rollover'")
print("Option C (code fix): In rule_service.py standardize_raw_input, also query business_type_master.ui_display_value directly")

# Count what is broken vs working
print("\n=== How many rule_master rows are affected? ===")
for r in q("SELECT COUNT(*) as c FROM rule_master WHERE business_type_code='BT_RO_RN'"):
    print(f"BT_RO_RN rows affected if fix not applied: {r['c']}")
for r in q("SELECT COUNT(*) as c FROM rule_master WHERE business_type_code='BT_NEW'"):
    print(f"BT_NEW rows (currently working): {r['c']}")

cur.close()
conn.close()
print("\nDone.")
