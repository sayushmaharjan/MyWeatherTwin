"""
Pydantic models for travel weather planning.
Includes: Travel Reports, Road Conditions, Travel Windows, Flight Delay Risk.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Tuple


class TravelReport(BaseModel):
    """Full travel weather report."""
    destination: str
    month: str = Field(default="", description="Travel month")
    start_date: str = Field(default="", description="Start date ISO string")
    end_date: str = Field(default="", description="End date ISO string")
    num_days: int = Field(default=1, description="Number of travel days")
    home_city: str = Field(default="", description="User home city")
    health_issues: str = Field(default="", description="User health issues")
    travel_mode: str = Field(default="Flight", description="Flight or Car")
    profile: str = Field(default="", description="Destination weather profile")
    packing_list: str = Field(default="", description="Health-aware packing recommendations")
    weather_twin: str = Field(default="", description="Most similar weather city")
    flight_risk: str = Field(default="Low", description="Travel risk assessment")
    itinerary: str = Field(default="", description="Day-by-day itinerary")
    weather_diff: str = Field(default="", description="Home vs destination weather comparison")
    route_coords: list = Field(default_factory=list, description="Driving route polyline coords")
    home_coords: Optional[Tuple[float, float]] = Field(default=None, description="Home lat/lon")
    dest_coords: Optional[Tuple[float, float]] = Field(default=None, description="Destination lat/lon")


# ── Road Condition Models ─────────────────────────

class BlackIceRisk(BaseModel):
    """Black ice probability assessment for a single hour."""
    risk_score: int = Field(ge=0, le=100)
    condition: str
    icon: str
    stopping_distance_multiplier: int = 1
    risk_factors: List[str] = Field(default_factory=list)
    surface_temp_c: Optional[float] = None
    air_temp_c: Optional[float] = None


class FogRisk(BaseModel):
    """Fog/visibility assessment for a single hour."""
    visibility_m: float = 10000
    density: str = "CLEAR"
    icon: str = "🟢"
    speed_advice: str = "Normal driving conditions"
    dew_spread: float = 10.0


class RoadConditionHour(BaseModel):
    """Combined road condition for one hour."""
    hour: int
    time_label: str
    ice: BlackIceRisk
    fog: FogRisk
    combined_danger: int = 0
    safe_to_drive: bool = True


class RoadConditions(BaseModel):
    """Full 24-hour road condition analysis."""
    hourly: List[RoadConditionHour] = Field(default_factory=list)
    worst_hour: Optional[RoadConditionHour] = None
    safe_hours_count: int = 24
    current: Optional[RoadConditionHour] = None
    peak_danger_time: str = ""
    peak_danger_score: int = 0


# ── Travel Window Models ──────────────────────────

class TravelWindowDay(BaseModel):
    """Single day in a travel corridor scoring."""
    day: str
    date: str
    corridor_score: int = 100
    worst_point: str = "origin"
    grade: str = "🟢 Excellent"
    origin_precip: float = 0
    dest_precip: float = 0
    origin_snow: float = 0


class TravelWindowResult(BaseModel):
    """Full 7-day travel window analysis."""
    daily_scores: List[TravelWindowDay] = Field(default_factory=list)
    best_travel_day: Optional[TravelWindowDay] = None
    trip_hours: float = 4.0


# ── Flight Delay Models ──────────────────────────

class FlightDelayRisk(BaseModel):
    """Flight delay risk for a single airport."""
    icao: str
    delay_risk_score: int = Field(ge=0, le=100, default=0)
    risk_level: str = "🟢 Low"
    delay_reasons: List[str] = Field(default_factory=list)
    visibility_sm: Optional[float] = None
    wind_kt: Optional[float] = None
    conditions_summary: str = "No significant weather"
    raw_temp_c: Optional[float] = None


class FlightDelayResult(BaseModel):
    """Combined origin + destination flight delay analysis."""
    origin: FlightDelayRisk
    destination: FlightDelayRisk
    overall_risk: int = 0
