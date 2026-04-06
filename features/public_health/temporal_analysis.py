"""
Temporal and Behavioral Analysis — trend detection, clustering, and pattern mining.

Analyzes:
  - Time-based trends and spikes in substance-related discussions
  - Behavioral clustering of posts by risk profile
  - Day-of-week, time-of-day, and monthly patterns
  - Emerging narrative detection
"""

import math
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
from collections import Counter, defaultdict


# ═══════════════════════════════════════════════════
#  Temporal Trend Analysis
# ═══════════════════════════════════════════════════

def compute_temporal_trends(df: pd.DataFrame) -> Dict:
    """
    Compute temporal trends including:
    - Monthly post volume and risk averages
    - Rolling averages
    - Spike detection
    """
    if df.empty or "created_utc" not in df.columns:
        return {"error": "No temporal data available"}

    df = df.copy()
    df["datetime"] = df["created_utc"].apply(
        lambda t: datetime.fromtimestamp(t) if pd.notna(t) else None
    )
    df = df.dropna(subset=["datetime"])

    if df.empty:
        return {"error": "No valid timestamps"}

    # Monthly aggregation
    df["year_month"] = df["datetime"].apply(lambda d: d.strftime("%Y-%m"))
    df["month"] = df["datetime"].apply(lambda d: d.month)
    df["day_of_week"] = df["datetime"].apply(lambda d: d.strftime("%A"))
    df["hour"] = df["datetime"].apply(lambda d: d.hour)

    monthly = df.groupby("year_month").agg(
        post_count=("post_id", "count"),
        avg_risk=("risk_score", "mean"),
        max_risk=("risk_score", "max"),
        high_risk_count=("risk_score", lambda x: (x >= 0.6).sum()),
    ).reset_index()

    # Rolling 3-month average for spike detection
    if len(monthly) >= 3:
        monthly["rolling_avg_risk"] = monthly["avg_risk"].rolling(3, min_periods=1).mean()
        monthly["rolling_avg_count"] = monthly["post_count"].rolling(3, min_periods=1).mean()
        # Spike: risk exceeds 1.3x rolling average
        monthly["is_spike"] = monthly["avg_risk"] > (monthly["rolling_avg_risk"] * 1.3)
    else:
        monthly["rolling_avg_risk"] = monthly["avg_risk"]
        monthly["rolling_avg_count"] = monthly["post_count"]
        monthly["is_spike"] = False

    spike_months = monthly[monthly["is_spike"] == True]["year_month"].tolist()

    return {
        "monthly_data": monthly.to_dict("records"),
        "spike_months": spike_months,
        "total_months": len(monthly),
        "overall_trend": _detect_trend_direction(monthly["avg_risk"].values),
    }


def compute_temporal_patterns(df: pd.DataFrame) -> Dict:
    """
    Compute granular temporal patterns:
    - Day of week distribution
    - Hour of day distribution
    - Monthly seasonality
    """
    if df.empty or "created_utc" not in df.columns:
        return {}

    df = df.copy()
    df["datetime"] = df["created_utc"].apply(
        lambda t: datetime.fromtimestamp(t) if pd.notna(t) else None
    )
    df = df.dropna(subset=["datetime"])

    if df.empty:
        return {}

    df["day_of_week"] = df["datetime"].apply(lambda d: d.strftime("%A"))
    df["hour"] = df["datetime"].apply(lambda d: d.hour)
    df["month_name"] = df["datetime"].apply(lambda d: d.strftime("%B"))
    df["month_num"] = df["datetime"].apply(lambda d: d.month)

    # Day of week analysis
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = df.groupby("day_of_week").agg(
        count=("post_id", "count"),
        avg_risk=("risk_score", "mean"),
    )
    dow = dow.reindex(day_order).fillna(0)
    peak_day = dow["avg_risk"].idxmax() if not dow.empty else "Unknown"

    # Hour of day analysis
    hour_data = df.groupby("hour").agg(
        count=("post_id", "count"),
        avg_risk=("risk_score", "mean"),
    ).reset_index()
    peak_hour = hour_data.loc[hour_data["avg_risk"].idxmax(), "hour"] if not hour_data.empty else 0

    # Time period labels
    def hour_period(h):
        if 6 <= h < 12:
            return "morning"
        elif 12 <= h < 17:
            return "afternoon"
        elif 17 <= h < 22:
            return "evening"
        else:
            return "night"

    df["time_period"] = df["hour"].apply(hour_period)
    period_data = df.groupby("time_period").agg(
        count=("post_id", "count"),
        avg_risk=("risk_score", "mean"),
    )

    # Monthly analysis
    month_data = df.groupby("month_num").agg(
        count=("post_id", "count"),
        avg_risk=("risk_score", "mean"),
    ).reset_index()
    month_data["month_name"] = month_data["month_num"].apply(
        lambda m: datetime(2020, m, 1).strftime("%B")
    )
    peak_month = month_data.loc[month_data["avg_risk"].idxmax(), "month_name"] if not month_data.empty else "Unknown"

    return {
        "day_of_week": {
            "data": dow.reset_index().to_dict("records"),
            "peak_day": peak_day,
        },
        "hour_of_day": {
            "data": hour_data.to_dict("records"),
            "peak_hour": int(peak_hour),
            "peak_period": hour_period(int(peak_hour)),
        },
        "time_period": period_data.to_dict("index") if not period_data.empty else {},
        "monthly": {
            "data": month_data.to_dict("records"),
            "peak_month": peak_month,
        },
    }


# ═══════════════════════════════════════════════════
#  Behavioral Clustering (TF-IDF + K-means style)
# ═══════════════════════════════════════════════════

def cluster_posts_by_behavior(df: pd.DataFrame, n_clusters: int = 5) -> List[Dict]:
    """
    Cluster posts by behavioral/topical similarity using a lightweight
    keyword-based approach (no heavy ML dependencies needed).

    Groups posts by their dominant substance categories and risk profiles.
    """
    if df.empty or "substance_categories" not in df.columns:
        return []

    df = df.copy()

    # Strategy: Rule-based clustering by substance + severity profile
    clusters = []

    # Cluster 1: Opioid-focused posts
    opioid_mask = df["substance_categories"].str.contains("opioid", case=False, na=False)
    if opioid_mask.sum() > 0:
        cluster_df = df[opioid_mask]
        clusters.append(_build_cluster(
            cluster_id=1,
            label="Opioid Dependency & Recovery",
            df=cluster_df,
        ))

    # Cluster 2: Alcohol-focused posts
    alcohol_mask = df["substance_categories"].str.contains("alcohol", case=False, na=False)
    if alcohol_mask.sum() > 0:
        cluster_df = df[alcohol_mask]
        clusters.append(_build_cluster(
            cluster_id=2,
            label="Alcohol Use & Sobriety",
            df=cluster_df,
        ))

    # Cluster 3: Cannabis-focused posts
    cannabis_mask = df["substance_categories"].str.contains("cannabis", case=False, na=False)
    if cannabis_mask.sum() > 0:
        cluster_df = df[cannabis_mask]
        clusters.append(_build_cluster(
            cluster_id=3,
            label="Cannabis Dependence",
            df=cluster_df,
        ))

    # Cluster 4: Emotional distress + substance co-occurrence
    distress_substance = (
        df["signal_types"].str.contains("emotional_distress", case=False, na=False) &
        df["signal_types"].str.contains("substance_mention", case=False, na=False)
    )
    if distress_substance.sum() > 0:
        cluster_df = df[distress_substance]
        clusters.append(_build_cluster(
            cluster_id=4,
            label="Co-occurring Distress & Substance Use",
            df=cluster_df,
        ))

    # Cluster 5: High-risk / critical posts
    high_risk = df["risk_score"] >= 0.6
    if high_risk.sum() > 0:
        cluster_df = df[high_risk]
        clusters.append(_build_cluster(
            cluster_id=5,
            label="High-Risk & Crisis Posts",
            df=cluster_df,
        ))

    # Cluster 6: Recovery-focused posts (low risk, substance mention)
    recovery_keywords = ["sober", "recovery", "clean", "day", "month", "year", "proud", "milestone"]
    recovery_mask = df["body"].fillna("").str.lower().apply(
        lambda t: any(kw in t for kw in recovery_keywords)
    ) & (df["risk_score"] < 0.4)
    if recovery_mask.sum() > 0:
        cluster_df = df[recovery_mask]
        clusters.append(_build_cluster(
            cluster_id=6,
            label="Recovery & Sobriety Milestones",
            df=cluster_df,
        ))

    return clusters


def _build_cluster(cluster_id: int, label: str, df: pd.DataFrame) -> Dict:
    """Build cluster summary from a subset of posts."""
    # Dominant substances
    substance_counts = _count_flat_categories(df.get("substance_categories", pd.Series()))
    dominant_substances = [s for s, _ in sorted(substance_counts.items(), key=lambda x: -x[1])[:3]]

    # Dominant emotions (from distress signals)
    emotion_counts = _count_flat_categories(df.get("signal_types", pd.Series()))

    # Top keywords
    keyword_counts = Counter()
    for kws in df.get("keywords_matched", pd.Series()).dropna():
        for kw in str(kws).split(", "):
            kw = kw.strip()
            if kw:
                keyword_counts[kw] += 1
    top_keywords = [k for k, _ in keyword_counts.most_common(8)]

    # Temporal pattern
    if "season" in df.columns:
        season_counts = df["season"].value_counts()
        peak_season = season_counts.index[0] if not season_counts.empty else "unknown"
        temporal_pattern = f"Peaks in {peak_season}"
    else:
        temporal_pattern = "Insufficient temporal data"

    # Weather correlation summary
    if "temperature_c" in df.columns and df["temperature_c"].notna().sum() > 5:
        avg_temp = df["temperature_c"].mean()
        weather_correlation = f"Average temperature: {avg_temp:.1f}°C"
    else:
        weather_correlation = "Insufficient weather data"

    return {
        "cluster_id": cluster_id,
        "cluster_label": label,
        "post_count": len(df),
        "dominant_substances": dominant_substances,
        "avg_severity": round(df["risk_score"].mean(), 3) if "risk_score" in df.columns else 0,
        "max_severity": round(df["risk_score"].max(), 3) if "risk_score" in df.columns else 0,
        "dominant_emotions": list(emotion_counts.keys())[:3],
        "top_keywords": top_keywords,
        "temporal_pattern": temporal_pattern,
        "weather_correlation": weather_correlation,
        "severity_distribution": df["risk_severity"].value_counts().to_dict() if "risk_severity" in df.columns else {},
    }


# ═══════════════════════════════════════════════════
#  Emerging Narrative Detection
# ═══════════════════════════════════════════════════

def detect_emerging_narratives(df: pd.DataFrame) -> List[Dict]:
    """
    Detect emerging discussion themes by analyzing keyword frequency
    changes over time.
    """
    if df.empty or "created_utc" not in df.columns or "keywords_matched" not in df.columns:
        return []

    df = df.copy()
    df["datetime"] = df["created_utc"].apply(
        lambda t: datetime.fromtimestamp(t) if pd.notna(t) else None
    )
    df = df.dropna(subset=["datetime"])
    df = df.sort_values("datetime")

    if len(df) < 20:
        return []

    # Split into first half and recent half
    midpoint = len(df) // 2
    early = df.iloc[:midpoint]
    recent = df.iloc[midpoint:]

    early_kw = _count_keywords(early)
    recent_kw = _count_keywords(recent)

    # Find keywords that increased significantly
    narratives = []
    for kw, recent_count in recent_kw.items():
        early_count = early_kw.get(kw, 0)
        if recent_count >= 3 and recent_count > early_count * 1.5:
            change_pct = ((recent_count - early_count) / max(early_count, 1)) * 100
            narratives.append({
                "keyword": kw,
                "early_count": early_count,
                "recent_count": recent_count,
                "change_pct": round(change_pct, 1),
                "direction": "increasing",
            })

    # Find keywords that decreased
    for kw, early_count in early_kw.items():
        recent_count = recent_kw.get(kw, 0)
        if early_count >= 3 and early_count > recent_count * 1.5:
            change_pct = ((recent_count - early_count) / max(early_count, 1)) * 100
            narratives.append({
                "keyword": kw,
                "early_count": early_count,
                "recent_count": recent_count,
                "change_pct": round(change_pct, 1),
                "direction": "decreasing",
            })

    # Sort by magnitude of change
    narratives.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return narratives[:15]


# ═══════════════════════════════════════════════════
#  State-Level Aggregation
# ═══════════════════════════════════════════════════

def aggregate_by_state(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate risk signals by US state for geographic analysis."""
    if df.empty or "location_state" not in df.columns:
        return pd.DataFrame()

    state_data = df.groupby("location_state").agg(
        post_count=("post_id", "count"),
        avg_risk=("risk_score", "mean"),
        max_risk=("risk_score", "max"),
        high_risk_count=("risk_score", lambda x: (x >= 0.6).sum()),
        critical_count=("risk_score", lambda x: (x >= 0.8).sum()),
    ).reset_index()

    state_data = state_data.sort_values("avg_risk", ascending=False)
    state_data = state_data.round(3)
    return state_data


# ═══════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════

def _detect_trend_direction(values: np.ndarray) -> str:
    """Detect if a series is trending up, down, or stable."""
    if len(values) < 3:
        return "insufficient data"

    # Simple linear regression
    x = np.arange(len(values), dtype=float)
    x_mean = np.mean(x)
    y_mean = np.mean(values)
    numerator = np.sum((x - x_mean) * (values - y_mean))
    denominator = np.sum((x - x_mean) ** 2)

    if denominator == 0:
        return "stable"

    slope = numerator / denominator

    if abs(slope) < 0.01:
        return "stable"
    elif slope > 0:
        return "increasing"
    else:
        return "decreasing"


def _count_flat_categories(series: pd.Series) -> Dict[str, int]:
    """Count categories from a comma-separated series."""
    counts = {}
    for val in series.dropna():
        for cat in str(val).split(", "):
            cat = cat.strip()
            if cat and cat != "none":
                counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _count_keywords(df: pd.DataFrame) -> Dict[str, int]:
    """Count keyword occurrences."""
    counts = Counter()
    for kws in df.get("keywords_matched", pd.Series()).dropna():
        for kw in str(kws).split(", "):
            kw = kw.strip()
            if kw and len(kw) > 2:
                counts[kw] += 1
    return dict(counts)
