# ============================================================
# MOTOR INSURANCE INFLOW API
# ============================================================
# File    : main.py
# Purpose : Entry point for the FastAPI application.
#           Master & Mapping API Layer — 12 read-only endpoints.
# ============================================================

from typing import List
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

# database.py exports:
#   test_connection() — for the /health route
#   get_db()          — dependency that gives routes a database session
from database import test_connection, get_db

from routes.rule_routes import router as rule_router
from routes.inflow_routes import router as inflow_router

from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------------
# Create the FastAPI application instance.
# -----------------------------------------------------------
app = FastAPI(
    title="Motor Insurance Inflow API",
    description="Rate Finder — Returns insurer inflow rates based on selected dimensions.",
    version="0.1.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Rule Master & Inflow Lookup routes
app.include_router(rule_router)
app.include_router(inflow_router)


# -----------------------------------------------------------
# SYSTEM HEALTH ROUTES
# -----------------------------------------------------------
@app.get("/")
def home():
    return {
        "message": "Motor Insurance Inflow API is running"
    }


@app.get("/health")
def health_check():
    db_status = test_connection()
    return {
        "api": "ok",
        **db_status
    }


# ============================================================
# 1. PRODUCT DOMAIN
# ============================================================
@app.get("/products")
def get_products(db: Session = Depends(get_db)):
    sql = text("""
        SELECT product_code, product_name, is_active
        FROM product_master
        ORDER BY product_code
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "products": [dict(row._mapping) for row in rows]
    }


@app.get("/product-mappings")
def get_product_mappings(db: Session = Depends(get_db)):
    sql = text("""
        SELECT original_value, product_code
        FROM product_mapping
        ORDER BY product_code, original_value
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "product_mappings": [dict(row._mapping) for row in rows]
    }


# ============================================================
# 2. SUBPRODUCT DOMAIN
# ============================================================
@app.get("/subproducts")
def get_subproducts(db: Session = Depends(get_db)):
    sql = text("""
        SELECT subproduct_code, subproduct_name, product_code, is_active
        FROM subproduct_master
        ORDER BY product_code, subproduct_code
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "subproducts": [dict(row._mapping) for row in rows]
    }


@app.get("/subproduct-mappings")
def get_subproduct_mappings(db: Session = Depends(get_db)):
    sql = text("""
        SELECT product_code, original_value, subproduct_code
        FROM subproduct_mapping
        ORDER BY product_code, subproduct_code
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "subproduct_mappings": [dict(row._mapping) for row in rows]
    }


# ============================================================
# 3. BUSINESS TYPE DOMAIN
# ============================================================
@app.get("/business-types")
def get_business_types(db: Session = Depends(get_db)):
    sql = text("""
        SELECT business_type_code, canonical_business_type, ui_display_value, is_active
        FROM business_type_master
        ORDER BY business_type_code
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "business_types": [dict(row._mapping) for row in rows]
    }


@app.get("/business-type-mappings")
def get_business_type_mappings(db: Session = Depends(get_db)):
    sql = text("""
        SELECT mapping_id, business_type_code, ui_display_value, source_rule_value, applicable_subline_code, mapping_type, is_active
        FROM business_type_mapping
        ORDER BY mapping_id
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "business_type_mappings": [dict(row._mapping) for row in rows]
    }


# ============================================================
# 4. STATE DOMAIN
# ============================================================
@app.get("/states")
def get_states(db: Session = Depends(get_db)):
    sql = text("""
        SELECT state_code, source_state, ui_display_value, is_active
        FROM state_master
        ORDER BY state_code
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "states": [dict(row._mapping) for row in rows]
    }


@app.get("/state-mappings")
def get_state_mappings(db: Session = Depends(get_db)):
    sql = text("""
        SELECT mapping_id, state_code, source_state, ui_display_value, is_active, mapping_type, match_normalization
        FROM state_mapping
        ORDER BY mapping_id
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "state_mappings": [dict(row._mapping) for row in rows]
    }


# ============================================================
# 5. LOCATION DOMAIN
# ============================================================
@app.get("/locations")
def get_locations(db: Session = Depends(get_db)):
    sql = text("""
        SELECT location_code, state_code, source_state, source_location, ui_display_value, location_type, is_active
        FROM location_master
        ORDER BY state_code, location_code
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "locations": [dict(row._mapping) for row in rows]
    }


@app.get("/location-mappings")
def get_location_mappings(db: Session = Depends(get_db)):
    sql = text("""
        SELECT mapping_id, location_code, state_code, source_state, source_location, ui_display_value, location_type, is_active, mapping_type, match_normalization
        FROM location_mapping
        ORDER BY mapping_id
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "location_mappings": [dict(row._mapping) for row in rows]
    }


# ============================================================
# 6. SUBLINE DOMAIN
# ============================================================
@app.get("/sublines")
def get_sublines(db: Session = Depends(get_db)):
    sql = text("""
        SELECT subline_code, source_subline, ui_display_value, is_active
        FROM subline_master
        ORDER BY subline_code
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "sublines": [dict(row._mapping) for row in rows]
    }


@app.get("/subline-mappings")
def get_subline_mappings(db: Session = Depends(get_db)):
    sql = text("""
        SELECT mapping_id, original_value, subline_code, ui_display_value, is_active
        FROM subline_mapping
        ORDER BY mapping_id
    """)
    rows = db.execute(sql).fetchall()
    return {
        "count": len(rows),
        "subline_mappings": [dict(row._mapping) for row in rows]
    }
