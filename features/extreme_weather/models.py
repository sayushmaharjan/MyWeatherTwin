"""
Pydantic models for extreme weather alerts.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class WeatherAlert(BaseModel):
    """A single extreme weather alert."""
    event: str = Field(description="Type of weather event (e.g., Tornado Warning)")
    severity: str = Field(description="Severity level: Minor, Moderate, Severe, Extreme")
    headline: str = Field(description="Short headline for the alert")
    description: str = Field(description="Detailed description of the alert")
    impact_score: int = Field(ge=1, le=10, description="Impact score from 1 (low) to 10 (catastrophic)")
    areas_affected: Optional[str] = Field(default=None, description="Areas affected")


class ExtremeWeatherReport(BaseModel):
    """Full extreme weather report for a city."""
    city: str
    alerts: List[WeatherAlert] = Field(default_factory=list)
    historical_comparison: str = Field(default="", description="LLM-generated historical comparison")
    overall_risk: str = Field(default="Low", description="Overall risk level")
