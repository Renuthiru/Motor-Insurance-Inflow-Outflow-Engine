# ============================================================
# schemas/rule_schema.py
# ============================================================
# Purpose: Pydantic request and response schemas for
#          Rule Lookup and End-to-End Inflow Lookup.
# ============================================================

from typing import List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------
# 1. Direct Standardized Rule Lookup Request
#    Requires all 7 standardized codes.
# -----------------------------------------------------------
class RuleLookupRequest(BaseModel):
    product_code: str = Field(..., example="PROD_2W", description="Standardized Product Code")
    subproduct_code: str = Field(..., example="SP_2W_BIKE", description="Standardized SubProduct Code")
    business_type_code: str = Field(..., example="BT_NEW", description="Standardized Business Type Code")
    rule_business_variant: str = Field(..., example="NEW(1+5)", description="Rule Business Variant")
    subline_code: str = Field(..., example="SL_PKG", description="Standardized SubLine Code")
    state_code: str = Field(..., example="ST_UK", description="Standardized State Code")
    location_code: str = Field(..., example="LOC_UK_ALL", description="Standardized Location Code")


# -----------------------------------------------------------
# 2. Raw Business Values Inflow Lookup Request
#    Accepts user-facing names (e.g., "Two Wheeler", "Bike")
# -----------------------------------------------------------
class RawInflowLookupRequest(BaseModel):
    product: Optional[str] = Field(None, example="Two Wheeler", description="Raw Product Name or Alias")
    subproduct: Optional[str] = Field(None, example="Bike", description="Raw SubProduct Name")
    business_type: Optional[str] = Field(None, example="New", description="Raw Business Type (New / Renewal / Rollover)")
    subline: Optional[str] = Field(None, example="Package", description="Raw SubLine (Package / SAOD / TP)")
    state: Optional[str] = Field(None, example="UTTARKHAND", description="Raw State Name")
    location: Optional[str] = Field(None, example="ROORKEE", description="Raw Location Name")
    rule_business_variant: Optional[str] = Field(None, example="NEW(1+5)", description="Optional specific business variant")


# -----------------------------------------------------------
# 3. Insurer Inflow Result
# -----------------------------------------------------------
class InsurerInflowResult(BaseModel):
    insurer: str = Field(..., example="CHOLA")
    inflow: str = Field(..., example="32.00%{NT(W/O CPA -2% Less - SUZUKI)}")


# -----------------------------------------------------------
# 4. Standardized Input Details (for debugging & transparency)
# -----------------------------------------------------------
class StandardizedCodesInfo(BaseModel):
    product_code: str
    subproduct_code: str
    business_type_code: str
    rule_business_variant: str
    subline_code: str
    state_code: str
    location_code: str


# -----------------------------------------------------------
# 5. Direct Standardized Rule Lookup Response
# -----------------------------------------------------------
class RuleLookupResponse(BaseModel):
    matched: bool
    count: int
    results: List[InsurerInflowResult] = []
    error: Optional[str] = None


# -----------------------------------------------------------
# 6. End-to-End Raw Inflow Lookup Response
# -----------------------------------------------------------
class RawInflowLookupResponse(BaseModel):
    matched: bool
    count: int
    standardized_input: Optional[StandardizedCodesInfo] = None
    results: List[InsurerInflowResult] = []
    error: Optional[str] = None
