"""
Pydantic models for agricultural weather intelligence.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class AgriculturalReport(BaseModel):
    """Full agricultural weather report."""
    city: str
    gdd: float = Field(default=0, description="Growing Degree Days accumulated")
    frost_risk_pct: int = Field(ge=0, le=100, description="Frost risk percentage")
    soil_moisture_est: str = Field(default="Normal", description="Soil moisture estimate")
    planting_window: str = Field(default="", description="Recommended planting window")
    advice: str = Field(default="", description="LLM-generated planting/farming advice")
    crop: Optional[str] = Field(default=None, description="Crop type if specified")


# ── Irrigation Scheduler ──────────────────────────

class IrrigationDay(BaseModel):
    """Single day in an irrigation schedule."""
    date: str
    et0_mm: float = 0
    crop_water_need_mm: float = 0
    effective_rain_mm: float = 0
    soil_moisture_pct: float = 0
    irrigate_today: bool = False
    deficit_mm: float = 0
    water_needed_liters: int = 0


class IrrigationSchedule(BaseModel):
    """Full 7-day irrigation schedule."""
    crop: str
    growth_stage: str
    area_hectares: float = 1.0
    schedule: List[IrrigationDay] = Field(default_factory=list)
    next_irrigation: Optional[IrrigationDay] = None
    weekly_water_need_mm: float = 0


# ── Livestock Heat Stress ─────────────────────────

class LivestockStressHour(BaseModel):
    """Hourly THI data point."""
    time: str
    temp_c: float
    humidity_pct: float
    thi: float
    level: str
    label: str
    impact: str = "Monitor conditions"


class LivestockStress(BaseModel):
    """Full livestock heat stress analysis."""
    species: str
    current_thi: float
    current_level: str
    peak_thi: float
    peak_time: str
    danger_hours_count: int = 0
    hourly_forecast: List[LivestockStressHour] = Field(default_factory=list)
    mitigations: List[str] = Field(default_factory=list)


# ── Crop Disease ──────────────────────────────────

class DiseaseAlert(BaseModel):
    """A single crop disease risk alert."""
    disease: str
    pathogen: str
    severity: str
    risk_percent: int
    hours_favorable: int
    affected_crops: List[str]
    action: str
    window_starts_in_hrs: int = 0


# ── Field Work Windows ────────────────────────────

class FieldWorkWindow(BaseModel):
    """Single day field work assessment."""
    date: str
    rain_mm: float = 0
    accumulated_dry_days: float = 0
    trafficable: bool = False
    frozen: bool = False
    compaction_risk: str = "High"
    wind_issue: Optional[bool] = None
    confidence: str = "Low"


# ── Harvest Quality ───────────────────────────────

class HarvestDay(BaseModel):
    """Single day harvest quality score."""
    date: str
    quality_score: int = 0
    grade: str = "D — Poor"
    rain_mm: float = 0
    avg_humidity_pct: float = 0
    risks: List[str] = Field(default_factory=list)
    harvest_recommended: bool = False


class HarvestQuality(BaseModel):
    """Full harvest quality prediction."""
    crop: str
    moisture_target_pct: float = 0
    windows: List[HarvestDay] = Field(default_factory=list)
    best_harvest_day: Optional[HarvestDay] = None
    rain_sensitivity: str = "MEDIUM"
