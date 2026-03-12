"""
Pydantic models for agricultural weather intelligence.
"""

from pydantic import BaseModel, Field
from typing import Optional


class AgriculturalReport(BaseModel):
    """Full agricultural weather report."""
    city: str
    gdd: float = Field(default=0, description="Growing Degree Days accumulated")
    frost_risk_pct: int = Field(ge=0, le=100, description="Frost risk percentage")
    soil_moisture_est: str = Field(default="Normal", description="Soil moisture estimate")
    planting_window: str = Field(default="", description="Recommended planting window")
    advice: str = Field(default="", description="LLM-generated planting/farming advice")
    crop: Optional[str] = Field(default=None, description="Crop type if specified")
