"""
Pydantic models for the Public Health Dashboard.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class OverdoseTrend(BaseModel):
    """State-level overdose trend analysis."""
    state: str
    substance_filter: Optional[str] = None
    total_records: int = 0
    latest_year: Optional[str] = None
    current_year_avg_monthly: Optional[float] = None
    yoy_change_pct: Optional[float] = None
    spike_months: List[str] = Field(default_factory=list)
    trend_data: List[dict] = Field(default_factory=list)
    substances_tracked: List[str] = Field(default_factory=list)


class SubstanceBreakdown(BaseModel):
    """Substance-level breakdown for a state."""
    substance_type: str
    total_deaths: float = 0
    months_reported: int = 0


class TreatmentFacility(BaseModel):
    """Nearby treatment facility."""
    name: str = "Treatment Facility"
    street1: str = ""
    city: str = ""
    state: str = ""
    phone: str = "Not listed"
    website: Optional[str] = None
    type_facility: str = "Not specified"
    distance_miles: float = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class PublicHealthAlert(BaseModel):
    """Proactive trend alert for a state."""
    has_alert: bool = False
    state: str = ""
    spike_detected: bool = False
    yoy_worsening: bool = False
    alert_text: str = ""
    yoy_change_pct: Optional[float] = None
