"""
Pydantic models for health-weather indices.
"""

from pydantic import BaseModel, Field


class HealthIndices(BaseModel):
    """All 7 health-weather indices for a location."""
    allergy_index: int = Field(ge=0, le=10, description="Allergy risk 0-10")
    asthma_risk: int = Field(ge=0, le=10, description="Asthma risk score 0-10")
    migraine_trigger: int = Field(ge=0, le=10, description="Migraine trigger score 0-10")
    heat_stress: int = Field(ge=0, le=10, description="Heat stress index 0-10")
    cold_exposure: int = Field(ge=0, le=10, description="Cold exposure risk 0-10")
    joint_pain: int = Field(ge=0, le=10, description="Joint pain predictor 0-10")
    sleep_quality: int = Field(ge=0, le=10, description="Sleep quality forecast 0-10 (10=best)")


class HealthReport(BaseModel):
    """Full health-weather report."""
    city: str
    indices: HealthIndices
    recommendation: str = Field(default="", description="LLM-generated health recommendation")
