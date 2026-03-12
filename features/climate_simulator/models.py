"""
Pydantic models for climate simulation scenarios.
"""

from pydantic import BaseModel, Field


class ClimateProjection(BaseModel):
    """Climate change projection for a city under a specific scenario."""
    city: str
    scenario: str = Field(description="IPCC scenario, e.g. SSP2-4.5")
    year: int = Field(description="Target year for projection")
    avg_high_change: str = Field(default="", description="Average high temp change")
    extreme_heat_days: str = Field(default="", description="Extreme heat days change")
    analog_city: str = Field(default="", description="Present-day climate analog city")
    narrative: str = Field(default="", description="AI-generated future narrative")
    key_impacts: str = Field(default="", description="Key impacts summary")
