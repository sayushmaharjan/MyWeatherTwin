"""
Pydantic models for the Public Health Dashboard.
Includes existing CDC/SAMHSA models + new Reddit risk analysis models.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


# ═══════════════════════════════════════════════════
#  Existing CDC / SAMHSA Models
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
#  Reddit Social Media Risk Analysis Models
# ═══════════════════════════════════════════════════

class RedditPost(BaseModel):
    """Individual Reddit post data for analysis."""
    post_id: str
    subreddit: str = ""
    title: str = ""
    body: str = ""
    author: str = "anonymous"
    created_utc: Optional[float] = None
    score: int = 0
    num_comments: int = 0
    label: str = ""  # From HuggingFace annotation
    source_dataset: str = ""  # Which dataset this came from
    location_state: str = ""  # Inferred or assigned US state


class RiskSignal(BaseModel):
    """Detected risk signal from a post."""
    post_id: str
    signal_type: str  # substance_mention, emotional_distress, slang_metaphor, relapse_signal
    substance_category: str = ""  # alcohol, opioids, cannabis, stimulants, etc.
    severity: str = "minimal"  # minimal, low, moderate, high, critical
    severity_score: float = 0.0  # 0.0 - 1.0
    evidence: str = ""  # The text snippet that triggered detection
    keywords_matched: List[str] = Field(default_factory=list)
    confidence: float = 0.0  # 0.0 - 1.0
    explanation: str = ""  # Why this was flagged


class WeatherContext(BaseModel):
    """Weather conditions at post time/location."""
    post_id: str
    state: str = ""
    date: str = ""
    temperature_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    weather_condition: str = ""
    is_extreme: bool = False
    season: str = ""  # winter, spring, summer, fall


class TemporalCluster(BaseModel):
    """Behavioral cluster from temporal analysis."""
    cluster_id: int
    cluster_label: str = ""
    post_count: int = 0
    dominant_substances: List[str] = Field(default_factory=list)
    avg_severity: float = 0.0
    dominant_emotions: List[str] = Field(default_factory=list)
    top_keywords: List[str] = Field(default_factory=list)
    temporal_pattern: str = ""  # e.g., "peaks in winter months"
    weather_correlation: str = ""  # e.g., "increases during cold weather"


class CorrelationResult(BaseModel):
    """Weather-substance correlation result."""
    weather_variable: str  # temperature, precipitation, humidity, etc.
    substance_category: str
    correlation_coefficient: float = 0.0
    p_value: Optional[float] = None
    strength: str = ""  # none, weak, moderate, strong
    direction: str = ""  # positive, negative
    interpretation: str = ""


class RiskReport(BaseModel):
    """Complete risk analysis report."""
    generated_at: str = ""
    total_posts_analyzed: int = 0
    total_risk_signals: int = 0
    dataset_sources: List[str] = Field(default_factory=list)

    # Risk distribution
    severity_distribution: Dict[str, int] = Field(default_factory=dict)
    substance_distribution: Dict[str, int] = Field(default_factory=dict)
    signal_type_distribution: Dict[str, int] = Field(default_factory=dict)

    # Weather correlations
    correlations: List[Dict] = Field(default_factory=list)
    weather_insights: List[str] = Field(default_factory=list)

    # Temporal patterns
    temporal_patterns: List[Dict] = Field(default_factory=list)
    clusters: List[Dict] = Field(default_factory=list)

    # Actionable insights
    key_findings: List[str] = Field(default_factory=list)
    intervention_recommendations: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    # Narrative sections (LLM-generated)
    executive_summary: str = ""
    detailed_analysis: str = ""
    weather_analysis_narrative: str = ""
    recommendations_narrative: str = ""
