"""
Pydantic models for travel weather planning.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class TravelReport(BaseModel):
    """Full travel weather report."""
    destination: str
    month: str = Field(default="", description="Travel month")
    profile: str = Field(default="", description="Destination weather profile")
    packing_list: str = Field(default="", description="LLM-generated packing recommendations")
    weather_twin: str = Field(default="", description="Most similar weather city")
    flight_risk: str = Field(default="Low", description="Flight disruption risk")
