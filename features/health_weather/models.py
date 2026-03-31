"""
Pydantic models for health-weather indices.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


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


# ── SAD Index ──────────────────────────────────────

class SADIndexResult(BaseModel):
    """Seasonal Affective Disorder risk assessment."""
    sad_index: int = Field(ge=0, le=100, description="SAD risk score 0-100")
    avg_sunshine_hrs_14d: float = Field(description="Average sunshine hours over last 14 days")
    consecutive_low_sun_days: int = Field(description="Consecutive days with < 1hr sunshine")
    risk_level: str = Field(description="Low / Moderate / High")
    recommendation: str = Field(description="Actionable advice")


# ── Medication Storage Alerts ──────────────────────

class MedicationAlert(BaseModel):
    """A single medication storage alert."""
    medication: str
    severity: str = Field(description="HIGH or MODERATE")
    issues: List[str]
    note: str


# ── Air Quality Composite ─────────────────────────

class AirQualityResult(BaseModel):
    """Air quality composite score with activity guidance."""
    us_aqi: Optional[int] = Field(default=None, description="US EPA AQI value")
    pm2_5: Optional[float] = Field(default=None, description="PM2.5 concentration")
    icon: str = Field(default="🟢", description="Status icon")
    tier: str = Field(default="Safe for all activity")
    activity_guidance: List[str] = Field(default_factory=list)
    worst_pollutant: str = Field(default="None")


# ── Outdoor Exercise Window ────────────────────────

class ExerciseWindow(BaseModel):
    """A scored exercise time window."""
    hour: int
    time_label: str
    score: int = Field(ge=0, le=100)
    temp_c: Optional[float] = None
    uv_index: Optional[float] = None
    precip_prob: Optional[float] = None


# ── Hydration Estimator ───────────────────────────

class HydrationResult(BaseModel):
    """Hydration needs estimate."""
    total_ml: int
    cups_8oz: int
    tip: str
