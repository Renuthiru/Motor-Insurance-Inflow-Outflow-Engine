"""
Fix: Add 'Renewal / Rollover' to business_type_mapping.

ROOT CAUSE: business_type_master has ui_display_value='Renewal / Rollover'
           but business_type_mapping only has 'Renewal' and 'Rollover' separately.
           The frontend dropdown displays 'Renewal / Rollover' from business_type_master.
           rule_service.py looks up business_type_mapping by ui_display_value.
           => 'Renewal / Rollover' is never found in business_type_mapping => BUG.

FIX: INSERT a mapping row for 'Renewal / Rollover' => BT_RO_RN.
     This is the canonical architecture: add to mapping table, not code hardcode.
"""
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

# --- Check current state before fix ---
print("=== BEFORE FIX ===")
print("Current business_type_mapping rows:")
for r in q("SELECT * FROM business_type_mapping ORDER BY mapping_id"):
    print(f"  {r['mapping_id']} | code={r['business_type_code']} | ui_display='{r['ui_display_value']}' | source_rule='{r['source_rule_value']}'")

# --- Check if fix already applied ---
existing = q("SELECT * FROM business_type_mapping WHERE ui_display_value='Renewal / Rollover'")
if existing:
    print("\nFix already applied — 'Renewal / Rollover' row already exists:")
    for r in existing:
        print(f"  {dict(r)}")
else:
    print("\nApplying fix: INSERT 'Renewal / Rollover' mapping row...")
    cur.execute("""
        INSERT INTO business_type_mapping
            (mapping_id, business_type_code, ui_display_value, source_rule_value, applicable_subline_code, mapping_type, is_active)
        VALUES
            ('BM_005', 'BT_RO_RN', 'Renewal / Rollover', 'RO/RN', 'ALL', 'UI_ALIAS', 'Y')
    """)
    conn.commit()
    print("  Inserted BM_005: 'Renewal / Rollover' => BT_RO_RN (source_rule=RO/RN)")

# --- Verify fix ---
print("\n=== AFTER FIX ===")
print("Current business_type_mapping rows:")
for r in q("SELECT * FROM business_type_mapping ORDER BY mapping_id"):
    print(f"  {r['mapping_id']} | code={r['business_type_code']} | ui_display='{r['ui_display_value']}' | source_rule='{r['source_rule_value']}'")

# --- Test the lookup that rule_service.py does ---
print("\n=== Testing rule_service.py lookup after fix ===")
val = 'Renewal / Rollover'
result = q("""
    SELECT business_type_code, source_rule_value, applicable_subline_code
    FROM business_type_mapping
    WHERE UPPER(TRIM(ui_display_value)) = UPPER(TRIM('Renewal / Rollover'))
       OR UPPER(TRIM(source_rule_value)) = UPPER(TRIM('Renewal / Rollover'))
       OR UPPER(TRIM(business_type_code)) = UPPER(TRIM('Renewal / Rollover'))
""")
print(f"Query result for 'Renewal / Rollover': {result}")
if result:
    print(f"  => business_type_code={result[0]['business_type_code']}, source_rule_value={result[0]['source_rule_value']}")
    print("  => std_variant will be derived as: 'RO/RN' (from BT_RO_RN logic in rule_service.py)")
    print("  FIX SUCCESSFUL!")
else:
    print("  STILL BROKEN - check mapping_id uniqueness or table schema")

cur.close()
conn.close()
print("\nDone.")
