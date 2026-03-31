"""
Health Weather — core business logic.
Computes health indices from weather data and generates recommendations via LLM.
Also includes: SAD Index, Medication Storage Alerts, Air Quality Composite,
Outdoor Exercise Windows, and Hydration Estimator.
"""

import requests
from datetime import datetime

from config import client, MODEL
from .models import (
    HealthIndices, HealthReport, SADIndexResult, MedicationAlert,
    AirQualityResult, ExerciseWindow, HydrationResult,
)


# ═══════════════════════════════════════════════════
#  EXISTING: Basic Health Indices
# ═══════════════════════════════════════════════════

def compute_health_indices(weather_data: dict) -> HealthIndices:
    """Calculate all 7 health-weather indices from current weather conditions."""
    cur = weather_data.get("current", {})
    temp_c = cur.get("temp_c", 20)
    humidity = cur.get("humidity", 50)
    wind_kph = cur.get("wind_kph", 10)
    pressure_mb = cur.get("pressure_mb", 1013)
    uv = cur.get("uv", 3)
    vis_km = cur.get("vis_km", 10)
    aqi_data = cur.get("air_quality", {})
    aqi = aqi_data.get("us-epa-index", 1) if isinstance(aqi_data, dict) else 1

    # Allergy: high humidity + moderate wind = worse
    allergy = min(10, int((humidity / 20) + (wind_kph / 15) + 1))

    # Asthma: driven by AQI + temperature extremes + humidity
    aqi_val = aqi if isinstance(aqi, (int, float)) else 1
    asthma = min(10, int(aqi_val * 1.5 + abs(temp_c - 22) / 10))

    # Migraine: rapid pressure changes (use deviation from 1013 as proxy)
    pressure_dev = abs(pressure_mb - 1013)
    migraine = min(10, int(pressure_dev / 5 + humidity / 30))

    # Heat stress: high temp + high humidity + high UV
    heat_stress = min(10, max(0, int((temp_c - 25) / 3 + humidity / 30 + uv / 4)))

    # Cold exposure: low temp + high wind
    cold_exposure = min(10, max(0, int((15 - temp_c) / 3 + wind_kph / 15)))

    # Joint pain: pressure drops + humidity shifts
    joint = min(10, int(pressure_dev / 4 + humidity / 25))

    # Sleep quality (inverted — 10 is best): comfortable temp + low humidity
    temp_comfort = max(0, 10 - abs(temp_c - 20))
    sleep = max(0, min(10, int(temp_comfort - humidity / 40 + 3)))

    return HealthIndices(
        allergy_index=max(0, allergy),
        asthma_risk=max(0, asthma),
        migraine_trigger=max(0, migraine),
        heat_stress=max(0, heat_stress),
        cold_exposure=max(0, cold_exposure),
        joint_pain=max(0, joint),
        sleep_quality=max(0, sleep),
    )


def get_health_recommendation(city: str, indices: HealthIndices, condition: str = "") -> str:
    """Use LLM to generate personalized health recommendation."""
    try:
        idx_summary = (
            f"Allergy: {indices.allergy_index}/10, Asthma: {indices.asthma_risk}/10, "
            f"Migraine: {indices.migraine_trigger}/10, Heat Stress: {indices.heat_stress}/10, "
            f"Cold Exposure: {indices.cold_exposure}/10, Joint Pain: {indices.joint_pain}/10, "
            f"Sleep Quality: {indices.sleep_quality}/10"
        )
        health_context = f"Health condition: {condition}" if condition else "General wellness"

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a health-weather advisor. Give brief, actionable health recommendations (max 300 chars) based on weather-health indices."},
                {"role": "user", "content": f"City: {city}. Indices: {idx_summary}. {health_context}. What should this person be aware of today?"},
            ],
            temperature=0.6,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Health recommendation unavailable."


def get_health_report(city: str, weather_data: dict, condition: str = "") -> HealthReport:
    """Full health-weather report for a city."""
    indices = compute_health_indices(weather_data)
    recommendation = get_health_recommendation(city, indices, condition)
    return HealthReport(city=city, indices=indices, recommendation=recommendation)


# ═══════════════════════════════════════════════════
#  NEW: Open-Meteo Data Fetchers
# ═══════════════════════════════════════════════════

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_openmeteo_health_data(lat: float, lon: float) -> dict:
    """Fetch sunshine/daylight/cloud data from Open-Meteo (30-day past + 7-day forecast)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["sunshine_duration", "cloudcover", "temperature_2m",
                    "relative_humidity_2m", "precipitation_probability",
                    "uv_index", "precipitation"],
        "daily": ["daylight_duration", "sunshine_duration",
                  "temperature_2m_max", "temperature_2m_min"],
        "past_days": 30,
        "forecast_days": 7,
        "timezone": "auto",
    }
    try:
        resp = requests.get(OPENMETEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def fetch_air_quality(lat: float, lon: float) -> dict:
    """Fetch air quality data from Open-Meteo Air Quality API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["pm2_5", "pm10", "ozone", "nitrogen_dioxide", "us_aqi"],
        "timezone": "auto",
        "forecast_days": 3,
    }
    try:
        resp = requests.get(AQ_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════
#  NEW FEATURE 1: SAD Index
# ═══════════════════════════════════════════════════

def compute_sad_index(daily_data: dict) -> SADIndexResult:
    """
    Compute Seasonal Affective Disorder risk score (0–100).
    Clinical threshold: <2 hrs sunshine/day for 2+ weeks = SAD risk zone.
    """
    sunshine_raw = daily_data.get("sunshine_duration", [])
    daylight_raw = daily_data.get("daylight_duration", [])

    if not sunshine_raw or len(sunshine_raw) < 14:
        return SADIndexResult(
            sad_index=0, avg_sunshine_hrs_14d=0, consecutive_low_sun_days=0,
            risk_level="Unknown", recommendation="Insufficient data to compute SAD index.",
        )

    sunshine_hours = [s / 3600 if s else 0 for s in sunshine_raw]  # seconds → hours

    last_14 = sunshine_hours[-14:]
    avg_sunshine = sum(last_14) / len(last_14)

    # Deficit ratio: how far below 2hr clinical threshold
    deficit_ratio = max(0, (2.0 - avg_sunshine) / 2.0)

    # Consecutive low-sun days (below 1hr) amplifies score
    consecutive_low = sum(1 for h in last_14 if h < 1.0)
    streak_penalty = min(consecutive_low * 4, 30)  # caps at 30 pts

    raw_score = (deficit_ratio * 70) + streak_penalty
    score = min(round(raw_score), 100)

    return SADIndexResult(
        sad_index=score,
        avg_sunshine_hrs_14d=round(avg_sunshine, 2),
        consecutive_low_sun_days=consecutive_low,
        risk_level="High" if score > 65 else "Moderate" if score > 35 else "Low",
        recommendation=_sad_recommendation(score, avg_sunshine),
    )


def _sad_recommendation(score: int, avg_sun: float) -> str:
    if score > 65:
        return "Consider a 10,000 lux light therapy lamp — 20–30 min each morning. Consult a doctor if symptoms persist."
    elif score > 35:
        return f"You're averaging {avg_sun:.1f} hrs of sun/day. Prioritize outdoor time during midday when possible."
    return "Sunlight exposure is adequate. Maintain outdoor habits."


# ═══════════════════════════════════════════════════
#  NEW FEATURE 2: Medication Storage Alerts
# ═══════════════════════════════════════════════════

MEDICATION_RULES = {
    "insulin": {
        "temp_min_c": 2, "temp_max_c": 30, "humidity_max": 80,
        "note": "Opened vials: room temp OK up to 30°C for 28 days. Unopened: refrigerate.",
    },
    "epinephrine": {
        "temp_min_c": 15, "temp_max_c": 25, "humidity_max": 75,
        "note": "EpiPen degrades above 25°C. Never leave in a hot car.",
    },
    "nitroglycerin": {
        "temp_min_c": 15, "temp_max_c": 25, "humidity_max": 70,
        "note": "Extremely heat and moisture sensitive. Keep in original container.",
    },
    "inhaler": {
        "temp_min_c": 15, "temp_max_c": 30, "humidity_max": 85,
        "note": "Cold reduces propellant effectiveness. Heat can cause canister to burst.",
    },
    "thyroid_medication": {
        "temp_min_c": 15, "temp_max_c": 25, "humidity_max": 60,
        "note": "Highly humidity-sensitive. Keep in airtight container.",
    },
}


def check_medication_alerts(weather: dict, user_meds: list) -> list:
    """Check current + forecast conditions against medication storage rules."""
    cur = weather.get("current", {})
    temp = cur.get("temp_c", cur.get("temperature_2m", 20))
    humidity = cur.get("humidity", cur.get("relative_humidity_2m", 50))

    # Also check next 6 hours from forecast if available
    hourly = weather.get("hourly", {})
    forecast_temps = hourly.get("temperature_2m", [])[:6]
    max_forecast_temp = max(forecast_temps) if forecast_temps else temp

    alerts = []
    for med in user_meds:
        med_key = med.lower().strip()
        if med_key not in MEDICATION_RULES:
            continue
        rule = MEDICATION_RULES[med_key]
        issues = []

        check_temp = max(temp, max_forecast_temp)  # worst case
        if check_temp > rule["temp_max_c"]:
            issues.append(f"Temperature ({check_temp:.1f}°C) exceeds safe storage limit of {rule['temp_max_c']}°C")
        if check_temp < rule["temp_min_c"]:
            issues.append(f"Temperature ({check_temp:.1f}°C) is below safe minimum of {rule['temp_min_c']}°C")
        if humidity > rule["humidity_max"]:
            issues.append(f"Humidity ({humidity}%) exceeds safe limit of {rule['humidity_max']}%")

        if issues:
            alerts.append(MedicationAlert(
                medication=med_key,
                severity="HIGH" if len(issues) > 1 else "MODERATE",
                issues=issues,
                note=rule["note"],
            ))

    return alerts


# ═══════════════════════════════════════════════════
#  NEW FEATURE 3: Air Quality Composite
# ═══════════════════════════════════════════════════

def compute_aq_composite(aq_data: dict) -> AirQualityResult:
    """Compute air quality composite score with activity tiers."""
    if "error" in aq_data:
        return AirQualityResult(
            us_aqi=None, pm2_5=None, icon="❓",
            tier="Air quality data unavailable",
            activity_guidance=["Data could not be fetched"],
            worst_pollutant="Unknown",
        )

    hourly = aq_data.get("hourly", {})
    current_hour = datetime.now().hour

    aqi_list = hourly.get("us_aqi", [])
    pm25_list = hourly.get("pm2_5", [])

    # Try to get current hour, fall back to first available
    idx = min(current_hour, len(aqi_list) - 1) if aqi_list else 0
    aqi = aqi_list[idx] if aqi_list else None
    pm25 = pm25_list[idx] if pm25_list else None

    if aqi is None:
        return AirQualityResult(
            us_aqi=None, pm2_5=None, icon="❓",
            tier="No AQI data available",
            activity_guidance=["Check back later"],
            worst_pollutant="Unknown",
        )

    # Activity safety tiers
    if aqi <= 50:
        tier, icon = "Safe for all activity", "🟢"
        activities = ["Running", "Cycling", "Children outdoor play", "Elderly outdoor time"]
    elif aqi <= 100:
        tier, icon = "Sensitive groups should limit strenuous activity", "🟡"
        activities = ["Walking OK", "Avoid prolonged running", "Asthma patients: carry inhaler"]
    elif aqi <= 150:
        tier, icon = "Unhealthy for sensitive groups", "🟠"
        activities = ["Keep outdoor time under 30 min", "Children/elderly stay indoors", "N95 if outside"]
    else:
        tier, icon = "Unhealthy — limit all outdoor activity", "🔴"
        activities = ["Work from home if possible", "N95 mandatory if outside", "Seal windows"]

    return AirQualityResult(
        us_aqi=int(aqi),
        pm2_5=round(pm25, 1) if pm25 else None,
        icon=icon,
        tier=tier,
        activity_guidance=activities,
        worst_pollutant="PM2.5" if (pm25 and pm25 > 35) else "Ozone" if aqi > 100 else "None",
    )


# ═══════════════════════════════════════════════════
#  NEW FEATURE 4: Outdoor Exercise Window
# ═══════════════════════════════════════════════════

def score_exercise_windows(hourly: dict, date: str = None) -> list:
    """Score each hour for exercise suitability (0–100). Returns top 3 windows."""
    times = hourly.get("time", [])
    if not times:
        return []

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Filter to requested date
    hours = [i for i, t in enumerate(times) if t.startswith(date)]
    if not hours:
        # Fallback: use first 24 hours available
        hours = list(range(min(24, len(times))))

    temp_list = hourly.get("temperature_2m", [])
    hum_list = hourly.get("relative_humidity_2m", [])
    uv_list = hourly.get("uv_index", [])
    precip_list = hourly.get("precipitation_probability", [])
    aqi_list = hourly.get("us_aqi", [])

    windows = []
    for i in hours:
        if i >= len(temp_list):
            continue
        temp = temp_list[i] if temp_list[i] is not None else 20
        humidity = hum_list[i] if i < len(hum_list) and hum_list[i] is not None else 50
        uv = uv_list[i] if i < len(uv_list) and uv_list[i] is not None else 3
        precip_prob = precip_list[i] if i < len(precip_list) and precip_list[i] is not None else 0
        aqi = aqi_list[i] if i < len(aqi_list) and aqi_list[i] is not None else 50

        # Score each factor (higher = better)
        temp_score = max(0, 100 - abs(temp - 18) * 4)     # ideal ~18°C
        humidity_score = max(0, 100 - humidity)              # lower humidity better
        uv_score = max(0, 100 - uv * 10)                    # UV<3 ideal
        rain_score = max(0, 100 - precip_prob)
        aqi_score = max(0, 100 - aqi)

        composite = (
            temp_score * 0.30 +
            humidity_score * 0.20 +
            uv_score * 0.20 +
            rain_score * 0.20 +
            aqi_score * 0.10
        )

        hour_of_day = i % 24
        windows.append(ExerciseWindow(
            hour=hour_of_day,
            time_label=f"{hour_of_day:02d}:00",
            score=round(composite),
            temp_c=round(temp, 1),
            uv_index=round(uv, 1) if uv else 0,
            precip_prob=round(precip_prob, 1) if precip_prob else 0,
        ))

    # Return top 3 windows
    return sorted(windows, key=lambda x: -x.score)[:3]


# ═══════════════════════════════════════════════════
#  NEW FEATURE 5: Hydration Estimator
# ═══════════════════════════════════════════════════

def compute_hydration(temp_c: float, humidity: float,
                      activity: str = "sedentary", weight_kg: float = 70.0) -> HydrationResult:
    """Estimate daily hydration needs based on weather + activity."""
    # Base: 35ml per kg body weight
    base_ml = weight_kg * 35

    # Heat adjustment (adds up to 750ml in extreme heat)
    heat_factor = max(0, (temp_c - 20) * 30)

    # Humidity adjustment (high humidity = more strain)
    humidity_factor = max(0, (humidity - 50) * 5)

    # Activity multipliers
    activity_factors = {
        "sedentary": 1.0, "light_walk": 1.2,
        "moderate_exercise": 1.5, "intense_exercise": 1.8,
    }
    activity_mul = activity_factors.get(activity, 1.0)

    total_ml = (base_ml + heat_factor + humidity_factor) * activity_mul
    cups = round(total_ml / 240)

    if temp_c > 28:
        tip = "Drink 500ml 2 hrs before going outside on hot days"
    else:
        tip = "Sip regularly — don't wait until thirsty"

    return HydrationResult(
        total_ml=round(total_ml),
        cups_8oz=cups,
        tip=tip,
    )
