"""
Pydantic models for smart recommendations.
"""

from pydantic import BaseModel, Field
from typing import List


class Recommendations(BaseModel):
    """Weather-based smart recommendations following the expert-guided structure."""
    smart_summary: str = Field(default="", description="2-3 line concise summary")
    health_alerts: List[str] = Field(default_factory=list, description="Personalized health alerts")
    commute_insights: List[str] = Field(default_factory=list, description="Weather-driven commute impacts")
    risk_score: str = Field(default="Low", description="Low / Moderate / High")
    recommendations: List[str] = Field(default_factory=list, description="Actionable suggestions")
    suggested_places: List[str] = Field(default_factory=list, description="Suggested venues for current weather")
    city: str = Field(default="")
