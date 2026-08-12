# ============================================================
# schemas/inflow_schema.py
# ============================================================
# Purpose: Pydantic schemas for the Inflow Calculation Engine.
# ============================================================

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


# -----------------------------------------------------------
# 1. Calculation Request Schema
# -----------------------------------------------------------
class InflowCalculationRequest(BaseModel):
    product: Optional[str] = Field(None, example="Two Wheeler", description="Raw Product Name")
    subproduct: Optional[str] = Field(None, example="Bike", description="Raw SubProduct Name")
    business_type: Optional[str] = Field(None, example="New", description="Raw Business Type")
    subline: Optional[str] = Field(None, example="Package", description="Raw SubLine Name")
    state: Optional[str] = Field(None, example="UTTARAKHAND", description="Raw State Name")
    location: Optional[str] = Field(None, example="DEHRADUN", description="Raw Location Name")
    
    # Vehicle specifications for evaluating rules
    vehicle_make: Optional[str] = Field(None, example="SUZUKI", description="Vehicle Manufacturer (e.g., SUZUKI, HERO)")
    vehicle_model: Optional[str] = Field(None, example="BOLERO", description="Vehicle Model (e.g., BOLERO)")
    engine_cc: Optional[int] = Field(None, example=125, description="Engine CC")
    gvw: Optional[float] = Field(None, example=12000, description="Gross Vehicle Weight (GVW) in kgs")
    cpa: Optional[bool] = Field(None, example=False, description="CPA Status (True/False)")
    vehicle_age: Optional[int] = Field(None, example=2, description="Vehicle Age in Years")
    coverage: Optional[str] = Field(None, example="NT", description="Optional coverage type to filter ('NT' or 'OD')")
    rule_business_variant: Optional[str] = Field(None, example="NEW(1+5)", description="Optional specific business variant")


# -----------------------------------------------------------
# 2. Individual Insurer Calculation Result
# -----------------------------------------------------------
class CalculatedInsurerResult(BaseModel):
    insurer: str = Field(..., example="CHOLA")
    rate: Optional[float] = Field(..., example=40.0, description="Evaluated Inflow Percentage Rate")
    matched_rule: Optional[str] = Field(..., example="40.00%{NT(W/O CPA -2% Less - SUZUKI - Upto 150cc)}")
    raw_inflow: Optional[str] = Field(None, description="Complete untruncated inflow expression from rule_master")
    conditions: Dict[str, Any] = Field(..., description="Details of conditions parsed from expression")


# -----------------------------------------------------------
# 3. Overall Calculation Response Schema
# -----------------------------------------------------------
class InflowCalculationResponse(BaseModel):
    matched: bool
    standardized_input: Optional[Dict[str, Any]] = None
    results: List[CalculatedInsurerResult] = []
    error: Optional[str] = None
