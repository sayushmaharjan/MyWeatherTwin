"""
Weather–Substance Use Correlation Analysis.

Fetches historical weather data for each post's inferred location/time,
then computes statistical correlations between weather variables and
substance-related risk signals.
"""

import math
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .reddit_data import STATE_COORDS


# ═══════════════════════════════════════════════════
#  Weather Data Fetching (Open-Meteo Historical API)
# ═══════════════════════════════════════════════════

HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"


def _get_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    elif month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    else:
        return "fall"


def fetch_weather_for_date_location(lat: float, lon: float, date_str: str) -> dict:
    """
    Fetch historical weather for a specific date and location using Open-Meteo.
    Returns dict with temperature, precipitation, humidity, wind, and weather code.
    """
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": date_str,
            "end_date": date_str,
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
                     "precipitation_sum,wind_speed_10m_max,weather_code",
            "timezone": "auto",
        }
        resp = requests.get(HISTORICAL_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return {}

        data = resp.json()
        daily = data.get("daily", {})
        if not daily.get("time"):
            return {}

        temp_mean = daily.get("temperature_2m_mean", [None])[0]
        temp_max = daily.get("temperature_2m_max", [None])[0]
        temp_min = daily.get("temperature_2m_min", [None])[0]
        precip = daily.get("precipitation_sum", [0])[0]
        wind = daily.get("wind_speed_10m_max", [0])[0]
        weather_code = daily.get("weather_code", [0])[0]

        month = int(date_str.split("-")[1])
        is_extreme = (
            (temp_mean is not None and (temp_mean > 35 or temp_mean < -10)) or
            (precip is not None and precip > 25) or
            (wind is not None and wind > 60) or
            (weather_code is not None and weather_code >= 95)
        )

        return {
            "date": date_str,
            "temperature_c": temp_mean,
            "temperature_max_c": temp_max,
            "temperature_min_c": temp_min,
            "precipitation_mm": precip or 0,
            "wind_speed_kmh": wind or 0,
            "weather_code": weather_code or 0,
            "is_extreme": is_extreme,
            "season": _get_season(month),
        }
    except Exception as e:
        print(f"⚠️ Weather fetch failed for {date_str} at ({lat},{lon}): {e}")
        return {}


def fetch_weather_for_posts(df: pd.DataFrame, sample_size: int = 100) -> pd.DataFrame:
    """
    Fetch weather data for a sample of posts. Uses sampling to avoid hitting
    API rate limits while maintaining statistical validity.

    Returns merged DataFrame with weather columns.
    """
    if df.empty or "created_utc" not in df.columns:
        return df

    # Determine unique state-date combinations to minimize API calls
    df = df.copy()
    df["post_date"] = df["created_utc"].apply(
        lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d") if pd.notna(t) else None
    )
    df["post_month"] = df["created_utc"].apply(
        lambda t: datetime.fromtimestamp(t).month if pd.notna(t) else None
    )

    # Group by state and month, fetch one sample per group
    state_date_groups = df.groupby(["location_state", "post_date"]).first().reset_index()

    # Sample to limit API calls
    if len(state_date_groups) > sample_size:
        state_date_groups = state_date_groups.sample(n=sample_size, random_state=42)

    print(f"🌤️ Fetching weather for {len(state_date_groups)} unique state-date combinations...")

    weather_cache = {}
    fetched = 0
    for _, row in state_date_groups.iterrows():
        state = row["location_state"]
        date_str = row["post_date"]

        if not date_str or pd.isna(date_str):
            continue

        cache_key = f"{state}_{date_str}"
        if cache_key in weather_cache:
            continue

        coords = STATE_COORDS.get(state)
        if not coords:
            continue

        # Check if date is within the historical API range (not future)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt > datetime.utcnow() - timedelta(days=5):
                continue  # Too recent for historical API
        except Exception:
            continue

        weather = fetch_weather_for_date_location(coords[0], coords[1], date_str)
        if weather:
            weather_cache[cache_key] = weather
            fetched += 1

        # Rate limiting
        if fetched % 20 == 0 and fetched > 0:
            print(f"   Fetched {fetched}/{len(state_date_groups)} weather records...")

    print(f"✅ Fetched {len(weather_cache)} weather records")

    # Merge weather data back to posts
    weather_cols = ["temperature_c", "temperature_max_c", "temperature_min_c",
                    "precipitation_mm", "wind_speed_kmh", "weather_code",
                    "is_extreme", "season"]

    for col in weather_cols:
        df[col] = None

    for idx, row in df.iterrows():
        cache_key = f"{row['location_state']}_{row.get('post_date', '')}"
        weather = weather_cache.get(cache_key, {})
        if weather:
            for col in weather_cols:
                df.at[idx, col] = weather.get(col)

    # Fill missing seasons from month
    df["season"] = df.apply(
        lambda r: r["season"] if pd.notna(r.get("season")) else
        (_get_season(int(r["post_month"])) if pd.notna(r.get("post_month")) else "unknown"),
        axis=1
    )

    return df


# ═══════════════════════════════════════════════════
#  Correlation Analysis
# ═══════════════════════════════════════════════════

def compute_correlations(df: pd.DataFrame) -> List[Dict]:
    """
    Compute Pearson and Spearman correlations between weather variables
    and risk scores / substance mention frequency.
    """
    if df.empty or "risk_score" not in df.columns:
        return []

    weather_vars = ["temperature_c", "precipitation_mm", "wind_speed_kmh"]
    results = []

    for w_var in weather_vars:
        if w_var not in df.columns:
            continue

        # Drop rows with missing weather data
        valid = df[[w_var, "risk_score"]].dropna()
        if len(valid) < 10:
            continue

        x = valid[w_var].astype(float).values
        y = valid["risk_score"].astype(float).values

        # Pearson correlation
        pearson_r = _pearson_correlation(x, y)

        # Spearman rank correlation
        spearman_r = _spearman_correlation(x, y)

        # Statistical significance (approximate p-value)
        n = len(x)
        p_val = _approximate_p_value(pearson_r, n)

        # Interpret
        strength = _interpret_correlation_strength(pearson_r)
        direction = "positive" if pearson_r > 0 else "negative" if pearson_r < 0 else "none"

        interpretation = _generate_interpretation(w_var, pearson_r, strength, direction)

        results.append({
            "weather_variable": w_var,
            "target_variable": "risk_score",
            "pearson_r": round(pearson_r, 4),
            "spearman_r": round(spearman_r, 4),
            "p_value": round(p_val, 6) if p_val is not None else None,
            "n_samples": n,
            "strength": strength,
            "direction": direction,
            "significant": p_val < 0.05 if p_val is not None else False,
            "interpretation": interpretation,
        })

    # Also compute correlations per substance category
    substance_cols = _get_substance_binary_cols(df)
    for substance, mask in substance_cols.items():
        for w_var in weather_vars:
            if w_var not in df.columns:
                continue

            valid_mask = df[w_var].notna()
            combined = valid_mask & True  # Ensure boolean
            valid_df = df[combined]

            if len(valid_df) < 10:
                continue

            x = valid_df[w_var].astype(float).values
            y = mask[combined].astype(float).values

            corr = _pearson_correlation(x, y)
            p_val = _approximate_p_value(corr, len(x))
            strength = _interpret_correlation_strength(corr)

            if strength != "negligible":
                results.append({
                    "weather_variable": w_var,
                    "target_variable": f"substance_{substance}",
                    "pearson_r": round(corr, 4),
                    "spearman_r": 0.0,
                    "p_value": round(p_val, 6) if p_val is not None else None,
                    "n_samples": len(x),
                    "strength": strength,
                    "direction": "positive" if corr > 0 else "negative",
                    "significant": p_val < 0.05 if p_val is not None else False,
                    "interpretation": f"{substance} mentions show {strength} {('positive' if corr > 0 else 'negative')} correlation with {w_var.replace('_', ' ')}",
                })

    return results


def analyze_seasonal_patterns(df: pd.DataFrame) -> Dict:
    """Analyze how substance use signals vary by season."""
    if df.empty or "season" not in df.columns or "risk_score" not in df.columns:
        return {}

    seasonal = df.groupby("season").agg(
        avg_risk=("risk_score", "mean"),
        post_count=("risk_score", "count"),
        high_risk_pct=("risk_score", lambda x: (x >= 0.6).mean() * 100),
    ).round(3)

    substance_by_season = {}
    for season in ["winter", "spring", "summer", "fall"]:
        season_df = df[df["season"] == season]
        if not season_df.empty and "substance_categories" in season_df.columns:
            cats = _count_categories(season_df["substance_categories"])
            substance_by_season[season] = cats

    return {
        "seasonal_risk": seasonal.to_dict("index"),
        "substance_by_season": substance_by_season,
    }


def analyze_extreme_weather_impact(df: pd.DataFrame) -> Dict:
    """Compare risk signals during extreme vs normal weather."""
    if "is_extreme" not in df.columns or "risk_score" not in df.columns:
        return {}

    extreme = df[df["is_extreme"] == True]
    normal = df[df["is_extreme"] != True]

    if extreme.empty or normal.empty:
        return {
            "extreme_count": len(extreme),
            "normal_count": len(normal),
            "insufficient_data": True,
        }

    return {
        "extreme_count": len(extreme),
        "normal_count": len(normal),
        "extreme_avg_risk": round(extreme["risk_score"].mean(), 3),
        "normal_avg_risk": round(normal["risk_score"].mean(), 3),
        "risk_difference": round(extreme["risk_score"].mean() - normal["risk_score"].mean(), 3),
        "extreme_high_risk_pct": round((extreme["risk_score"] >= 0.6).mean() * 100, 1),
        "normal_high_risk_pct": round((normal["risk_score"] >= 0.6).mean() * 100, 1),
    }


def generate_weather_insights(correlations: List[Dict], seasonal: Dict,
                               extreme_impact: Dict) -> List[str]:
    """Generate human-readable weather-substance insights."""
    insights = []

    # Correlation insights
    sig_correlations = [c for c in correlations if c.get("significant")]
    for c in sig_correlations:
        w_var = c["weather_variable"].replace("_c", "").replace("_mm", "").replace("_kmh", "")
        w_var = w_var.replace("_", " ").title()
        insights.append(
            f"📊 {c['interpretation']} (r={c['pearson_r']}, p={c.get('p_value', 'N/A')})"
        )

    # Seasonal insights
    if seasonal and "seasonal_risk" in seasonal:
        risk_by_season = seasonal["seasonal_risk"]
        if risk_by_season:
            highest = max(risk_by_season.items(), key=lambda x: x[1].get("avg_risk", 0))
            lowest = min(risk_by_season.items(), key=lambda x: x[1].get("avg_risk", 0))
            insights.append(
                f"📅 Highest average risk score observed in **{highest[0]}** "
                f"({highest[1].get('avg_risk', 0):.3f}), lowest in **{lowest[0]}** "
                f"({lowest[1].get('avg_risk', 0):.3f})"
            )

    # Extreme weather insights
    if extreme_impact and not extreme_impact.get("insufficient_data"):
        diff = extreme_impact.get("risk_difference", 0)
        if abs(diff) > 0.05:
            direction = "higher" if diff > 0 else "lower"
            insights.append(
                f"⚡ During extreme weather events, average risk score is {abs(diff):.3f} "
                f"**{direction}** than normal conditions "
                f"({extreme_impact.get('extreme_avg_risk', 0):.3f} vs {extreme_impact.get('normal_avg_risk', 0):.3f})"
            )

    if not insights:
        insights.append("📊 No statistically significant weather-substance correlations detected in this dataset")

    return insights


# ═══════════════════════════════════════════════════
#  Statistical Utilities
# ═══════════════════════════════════════════════════

def _pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation coefficient."""
    if len(x) < 2:
        return 0.0
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    x_dev = x - x_mean
    y_dev = y - y_mean
    numerator = np.sum(x_dev * y_dev)
    denominator = math.sqrt(np.sum(x_dev ** 2) * np.sum(y_dev ** 2))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _spearman_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Spearman rank correlation coefficient."""
    if len(x) < 2:
        return 0.0
    x_ranks = _rank_data(x)
    y_ranks = _rank_data(y)
    return _pearson_correlation(x_ranks, y_ranks)


def _rank_data(data: np.ndarray) -> np.ndarray:
    """Rank data for Spearman correlation."""
    n = len(data)
    ranked = np.empty(n)
    sorted_indices = np.argsort(data)
    for rank, idx in enumerate(sorted_indices):
        ranked[idx] = rank + 1
    return ranked


def _approximate_p_value(r: float, n: int) -> Optional[float]:
    """Approximate two-tailed p-value for correlation using t-distribution."""
    if n < 3 or abs(r) >= 1.0:
        return None
    t_stat = r * math.sqrt(n - 2) / math.sqrt(1 - r ** 2)
    # Approximate p-value using normal approximation for large n
    p = 2 * (1 - _normal_cdf(abs(t_stat)))
    return max(p, 1e-10)


def _normal_cdf(x: float) -> float:
    """Approximate standard normal CDF using the error function approximation."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _interpret_correlation_strength(r: float) -> str:
    """Interpret correlation coefficient magnitude."""
    abs_r = abs(r)
    if abs_r < 0.1:
        return "negligible"
    elif abs_r < 0.3:
        return "weak"
    elif abs_r < 0.5:
        return "moderate"
    elif abs_r < 0.7:
        return "strong"
    else:
        return "very strong"


def _generate_interpretation(var_name: str, r: float, strength: str, direction: str) -> str:
    """Generate a plain-English interpretation of a correlation."""
    var_label = var_name.replace("_c", "").replace("_mm", "").replace("_kmh", "")
    var_label = var_label.replace("_", " ")

    if strength == "negligible":
        return f"No meaningful correlation between {var_label} and substance risk"

    if var_name == "temperature_c":
        if direction == "positive":
            return f"Higher temperatures show {strength} association with increased substance risk signals"
        else:
            return f"Lower temperatures (cold weather) show {strength} association with increased substance risk signals"
    elif var_name == "precipitation_mm":
        if direction == "positive":
            return f"Rainy/wet conditions show {strength} association with increased substance risk signals"
        else:
            return f"Dry conditions show {strength} association with increased substance risk signals"
    elif var_name == "wind_speed_kmh":
        if direction == "positive":
            return f"Windy conditions show {strength} association with increased substance risk signals"
        else:
            return f"Calm conditions show {strength} association with increased substance risk signals"
    else:
        return f"{var_label.title()} shows {strength} {direction} correlation with substance risk"


def _get_substance_binary_cols(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """Create binary columns for each substance category."""
    categories = ["alcohol", "opioids", "cannabis", "stimulants", "benzodiazepines",
                   "tobacco_nicotine", "general_substance"]
    result = {}
    for cat in categories:
        mask = df["substance_categories"].str.contains(cat, case=False, na=False)
        if mask.sum() > 5:
            result[cat] = mask.astype(int)
    return result


def _count_categories(series: pd.Series) -> Dict[str, int]:
    """Count substance category mentions from a comma-separated column."""
    counts = {}
    for val in series:
        if val and val != "none":
            for cat in val.split(", "):
                cat = cat.strip()
                if cat:
                    counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))
