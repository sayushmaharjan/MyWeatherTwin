"""
Agriculture — core business logic.
GDD calculation, frost risk, soil moisture estimation, and LLM planting advice.
Also includes: Irrigation Scheduler, Livestock Heat Stress, Crop Disease Calendar,
Field Work Windows, and Harvest Quality Predictor.
"""

import requests
from datetime import datetime

from config import client, MODEL
from .models import (
    AgriculturalReport, IrrigationDay, IrrigationSchedule,
    LivestockStressHour, LivestockStress, DiseaseAlert,
    FieldWorkWindow, HarvestDay, HarvestQuality,
)


# ═══════════════════════════════════════════════════
#  EXISTING: Basic Agriculture Functions
# ═══════════════════════════════════════════════════

def compute_growing_degree_days(temp_c: float, base_temp: float = 10.0) -> float:
    """Compute GDD contribution for a single day. base_temp defaults to 10°C."""
    return max(0, temp_c - base_temp)


def estimate_frost_risk(temp_c: float, wind_kph: float, humidity: int) -> int:
    """Estimate frost risk percentage from current conditions."""
    if temp_c > 5:
        return 0
    risk = max(0, int((5 - temp_c) * 15))
    if wind_kph < 5:
        risk += 10  # still air = more frost
    if humidity > 80:
        risk += 5
    return min(100, risk)


def estimate_soil_moisture(temp_c: float, precip_mm: float, humidity: int) -> str:
    """Simple soil moisture estimation."""
    if precip_mm > 10:
        return "Wet"
    elif precip_mm > 2:
        return "Moist"
    elif temp_c > 30 and humidity < 30:
        return "Dry"
    else:
        return "Normal"


def get_agriculture_report(city: str, weather_data: dict, crop: str = "") -> AgriculturalReport:
    """Generate a full agricultural weather report."""
    cur = weather_data.get("current", {})
    temp_c = cur.get("temp_c", 20)
    wind_kph = cur.get("wind_kph", 10)
    humidity = cur.get("humidity", 50)
    precip_mm = cur.get("precip_mm", 0)

    gdd = compute_growing_degree_days(temp_c)
    frost_risk = estimate_frost_risk(temp_c, wind_kph, humidity)
    soil_moisture = estimate_soil_moisture(temp_c, precip_mm, humidity)
    advice, planting_window = _get_planting_advice(city, crop, temp_c, frost_risk)

    return AgriculturalReport(
        city=city,
        gdd=round(gdd, 1),
        frost_risk_pct=frost_risk,
        soil_moisture_est=soil_moisture,
        planting_window=planting_window,
        advice=advice,
        crop=crop or None,
    )


def _get_planting_advice(city: str, crop: str, temp_c: float, frost_risk: int) -> tuple:
    """Use LLM to generate planting advice and window."""
    crop_info = f" for {crop}" if crop else ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an agricultural advisor. Give brief planting advice (max 400 chars). Include a recommended planting window on the last line prefixed with 'WINDOW:'."},
                {"role": "user", "content": f"City: {city}. Current temp: {temp_c}°C. Frost risk: {frost_risk}%. Give planting advice{crop_info}."},
            ],
            temperature=0.5,
            max_tokens=200,
        )
        text = response.choices[0].message.content.strip()
        # Extract planting window
        lines = text.split("\n")
        window = ""
        advice_lines = []
        for line in lines:
            if line.strip().upper().startswith("WINDOW:"):
                window = line.split(":", 1)[1].strip()
            else:
                advice_lines.append(line)
        return "\n".join(advice_lines), window
    except Exception:
        return "Planting advice unavailable.", ""


# ═══════════════════════════════════════════════════
#  NEW: Open-Meteo Agriculture Data Fetcher
# ═══════════════════════════════════════════════════

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_agriculture_data(lat: float, lon: float) -> dict:
    """Fetch agriculture-specific weather data from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m", "relative_humidity_2m",
            "wind_speed_10m", "shortwave_radiation",
            "precipitation",
        ],
        "daily": [
            "et0_fao_evapotranspiration", "precipitation_sum",
            "temperature_2m_max", "temperature_2m_min",
            "rain_sum",
        ],
        "past_days": 7,
        "forecast_days": 7,
        "timezone": "auto",
    }
    try:
        resp = requests.get(OPENMETEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════
#  NEW FEATURE 1: Irrigation Scheduler
# ═══════════════════════════════════════════════════

# Kc values from FAO-56 standard
CROP_KC = {
    "corn":          {"initial": 0.3, "mid": 1.20, "late": 0.35, "root_depth_m": 1.0},
    "wheat":         {"initial": 0.3, "mid": 1.15, "late": 0.25, "root_depth_m": 1.0},
    "soybeans":      {"initial": 0.4, "mid": 1.15, "late": 0.50, "root_depth_m": 0.9},
    "tomatoes":      {"initial": 0.6, "mid": 1.15, "late": 0.70, "root_depth_m": 0.7},
    "potatoes":      {"initial": 0.5, "mid": 1.15, "late": 0.65, "root_depth_m": 0.5},
    "cotton":        {"initial": 0.35, "mid": 1.20, "late": 0.50, "root_depth_m": 1.0},
    "grass/pasture": {"initial": 0.9, "mid": 1.00, "late": 1.00, "root_depth_m": 0.3},
    "vegetables":    {"initial": 0.5, "mid": 1.00, "late": 0.80, "root_depth_m": 0.4},
}

SOIL_WHC = {
    "sandy": 100, "sandy_loam": 130, "loam": 170,
    "clay_loam": 190, "clay": 200,
}


def compute_irrigation_schedule(
    ag_data: dict, crop: str = "corn", growth_stage: str = "mid",
    soil_type: str = "loam", area_hectares: float = 1.0,
) -> IrrigationSchedule:
    """Compute 7-day irrigation schedule using FAO-56 methodology."""
    daily = ag_data.get("daily", {})
    et0_list = daily.get("et0_fao_evapotranspiration", [])
    rain_list = daily.get("rain_sum", [])
    time_list = daily.get("time", [])

    crop_data = CROP_KC.get(crop, CROP_KC["corn"])
    kc = crop_data.get(growth_stage, crop_data["mid"])
    root_depth = crop_data["root_depth_m"]
    whc = SOIL_WHC.get(soil_type, 170)

    field_capacity = whc * root_depth
    soil_moisture_mm = field_capacity * 0.70  # start at 70%
    mad_threshold = field_capacity * 0.50

    schedule = []
    # Use the forecast portion (last 7 days of the 14-day window)
    start_idx = max(0, len(et0_list) - 7)

    for i in range(start_idx, min(start_idx + 7, len(et0_list))):
        et0 = et0_list[i] if et0_list[i] is not None else 0
        rain = rain_list[i] if i < len(rain_list) and rain_list[i] is not None else 0
        date = time_list[i] if i < len(time_list) else f"Day {i - start_idx + 1}"

        etc = et0 * kc
        effective_rain = rain * 0.75

        soil_moisture_mm = soil_moisture_mm - etc + effective_rain
        soil_moisture_mm = min(soil_moisture_mm, field_capacity)

        irrigate = soil_moisture_mm < mad_threshold
        deficit_mm = max(0, field_capacity - soil_moisture_mm)
        water_liters = int(deficit_mm * area_hectares * 10) if irrigate else 0

        schedule.append(IrrigationDay(
            date=date,
            et0_mm=round(et0, 2),
            crop_water_need_mm=round(etc, 2),
            effective_rain_mm=round(effective_rain, 2),
            soil_moisture_pct=round((soil_moisture_mm / field_capacity) * 100, 1),
            irrigate_today=irrigate,
            deficit_mm=round(deficit_mm, 2),
            water_needed_liters=water_liters,
        ))

    next_irrigation = next((d for d in schedule if d.irrigate_today), None)

    return IrrigationSchedule(
        crop=crop,
        growth_stage=growth_stage,
        area_hectares=area_hectares,
        schedule=schedule,
        next_irrigation=next_irrigation,
        weekly_water_need_mm=round(sum(d.crop_water_need_mm for d in schedule), 1),
    )


# ═══════════════════════════════════════════════════
#  NEW FEATURE 2: Livestock Heat Stress (THI)
# ═══════════════════════════════════════════════════

SPECIES_THRESHOLDS = {
    "dairy_cattle": {
        "comfortable": {"max": 68}, "alert": {"max": 72},
        "danger": {"max": 80}, "emergency": {"max": 999},
        "impacts": {
            "alert": "Milk production drops 10–15%",
            "danger": "Milk drops 25%+, conception rates fall",
            "emergency": "Risk of death. Immediate intervention required",
        },
    },
    "beef_cattle": {
        "comfortable": {"max": 70}, "alert": {"max": 74},
        "danger": {"max": 79}, "emergency": {"max": 999},
    },
    "poultry": {
        "comfortable": {"max": 70}, "alert": {"max": 75},
        "danger": {"max": 80}, "emergency": {"max": 999},
        "impacts": {
            "alert": "Feed intake drops, egg production falls",
            "danger": "Panting, reduced egg weight, mortality risk rises",
            "emergency": "Mass mortality possible within hours",
        },
    },
    "swine": {
        "comfortable": {"max": 74}, "alert": {"max": 78},
        "danger": {"max": 84}, "emergency": {"max": 999},
    },
}


def compute_thi(temp_c: float, humidity: float) -> float:
    """Standard THI formula used by USDA."""
    temp_f = (temp_c * 9 / 5) + 32
    return (0.8 * temp_f) + ((humidity / 100) * (temp_f - 14.4)) + 46.4


def classify_thi(thi: float, species: str) -> dict:
    thresholds = SPECIES_THRESHOLDS.get(species, SPECIES_THRESHOLDS["dairy_cattle"])
    labels = {"comfortable": "✅ Comfortable", "alert": "⚠️ Alert",
              "danger": "🟠 Danger", "emergency": "🔴 Emergency"}
    for level in ["comfortable", "alert", "danger", "emergency"]:
        if thi <= thresholds[level]["max"]:
            impacts = thresholds.get("impacts", {})
            return {
                "level": level,
                "label": labels.get(level, level),
                "impact": impacts.get(level, "Monitor conditions"),
            }
    return {"level": "emergency", "label": "🔴 Emergency", "impact": "Immediate action required"}


def compute_livestock_heat_stress(ag_data: dict, species: str = "dairy_cattle") -> LivestockStress:
    """Compute 48-hour livestock heat stress analysis."""
    hourly = ag_data.get("hourly", {})
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    times = hourly.get("time", [])

    results = []
    for i in range(min(48, len(temps))):
        temp = temps[i] if temps[i] is not None else 20
        hum = humidities[i] if i < len(humidities) and humidities[i] is not None else 50
        thi = compute_thi(temp, hum)
        classification = classify_thi(thi, species)
        time_str = times[i] if i < len(times) else f"Hour {i}"

        results.append(LivestockStressHour(
            time=time_str, temp_c=round(temp, 1), humidity_pct=round(hum, 1),
            thi=round(thi, 1), **classification,
        ))

    if not results:
        return LivestockStress(
            species=species, current_thi=0, current_level="Unknown",
            peak_thi=0, peak_time="N/A",
        )

    peak = max(results, key=lambda x: x.thi)
    danger_hours = [r for r in results if r.level in ["danger", "emergency"]]
    mitigations = _get_mitigation_advice(peak.level, species)

    return LivestockStress(
        species=species,
        current_thi=results[0].thi,
        current_level=results[0].label,
        peak_thi=peak.thi,
        peak_time=peak.time,
        danger_hours_count=len(danger_hours),
        hourly_forecast=results[:24],
        mitigations=mitigations,
    )


def _get_mitigation_advice(level: str, species: str) -> list:
    base = {
        "alert": [
            "Ensure continuous access to fresh, cool water",
            "Increase ventilation in barns/sheds",
            "Schedule feeding during cooler morning/evening hours",
        ],
        "danger": [
            "Activate all fans and evaporative cooling systems",
            "Add electrolytes to drinking water",
            "Reduce stocking density if possible",
            "Delay any transportation or handling",
        ],
        "emergency": [
            "🚨 Emergency cooling required immediately",
            "Spray animals with cool water every 30 minutes",
            "Contact your veterinarian",
            "Move animals to shaded/air-conditioned areas",
            "Do NOT move or handle animals unless necessary",
        ],
    }
    return base.get(level, ["Conditions are comfortable — routine monitoring"])


# ═══════════════════════════════════════════════════
#  NEW FEATURE 3: Crop Disease Calendar
# ═══════════════════════════════════════════════════

DISEASE_RULES = {
    "late_blight_tomato": {
        "name": "Late Blight (Tomato/Potato)", "crops": ["tomatoes", "potatoes"],
        "conditions": {"temp_min_c": 10, "temp_max_c": 24, "humidity_min": 90,
                       "consecutive_hours": 10, "rain_mm_trigger": 2.0},
        "severity": "HIGH",
        "action": "Apply fungicide within 24hrs. Remove infected leaves immediately.",
        "pathogen": "Phytophthora infestans",
    },
    "gray_mold": {
        "name": "Gray Mold (Botrytis)", "crops": ["tomatoes", "strawberries", "grapes", "vegetables"],
        "conditions": {"temp_min_c": 15, "temp_max_c": 25, "humidity_min": 85,
                       "consecutive_hours": 8, "rain_mm_trigger": 1.0},
        "severity": "HIGH",
        "action": "Improve air circulation. Apply fungicide. Remove dead plant material.",
        "pathogen": "Botrytis cinerea",
    },
    "corn_blight": {
        "name": "Northern Corn Leaf Blight", "crops": ["corn"],
        "conditions": {"temp_min_c": 18, "temp_max_c": 27, "humidity_min": 80,
                       "consecutive_hours": 12, "rain_mm_trigger": 5.0},
        "severity": "MEDIUM",
        "action": "Scout fields. Consider fungicide at tasseling if >50% plants infected.",
        "pathogen": "Exserohilum turcicum",
    },
    "powdery_mildew": {
        "name": "Powdery Mildew", "crops": ["wheat", "grapes", "vegetables", "soybeans"],
        "conditions": {"temp_min_c": 15, "temp_max_c": 28, "humidity_min": 70,
                       "consecutive_hours": 6, "rain_mm_trigger": 0},
        "severity": "MEDIUM",
        "action": "Apply sulfur-based fungicide. Avoid overhead irrigation.",
        "pathogen": "Various Erysiphe species",
    },
    "wheat_rust": {
        "name": "Wheat Rust", "crops": ["wheat"],
        "conditions": {"temp_min_c": 15, "temp_max_c": 22, "humidity_min": 95,
                       "consecutive_hours": 6, "rain_mm_trigger": 1.0},
        "severity": "HIGH",
        "action": "Apply fungicide immediately. Report to local extension office.",
        "pathogen": "Puccinia spp.",
    },
    "soybean_sclerotinia": {
        "name": "White Mold (Sclerotinia)", "crops": ["soybeans"],
        "conditions": {"temp_min_c": 15, "temp_max_c": 25, "humidity_min": 85,
                       "consecutive_hours": 10, "rain_mm_trigger": 3.0},
        "severity": "HIGH",
        "action": "Apply fungicide at early flowering. Improve field drainage.",
        "pathogen": "Sclerotinia sclerotiorum",
    },
}


def compute_disease_risk(ag_data: dict, user_crops: list) -> list:
    """Scan 72-hour forecast for crop disease risk conditions."""
    hourly = ag_data.get("hourly", {})
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    precips = hourly.get("precipitation", [])
    alerts = []

    for disease_key, disease in DISEASE_RULES.items():
        if not any(c in disease["crops"] for c in user_crops):
            continue

        cond = disease["conditions"]
        hours_at_risk = 0
        total_rain = 0

        scan_len = min(72, len(temps))
        for i in range(scan_len):
            temp = temps[i] if temps[i] is not None else 20
            humidity = humidities[i] if i < len(humidities) and humidities[i] is not None else 50
            rain = precips[i] if i < len(precips) and precips[i] is not None else 0

            total_rain += rain
            in_temp_range = cond["temp_min_c"] <= temp <= cond["temp_max_c"]
            in_humidity_range = humidity >= cond["humidity_min"]

            if in_temp_range and in_humidity_range:
                hours_at_risk += 1
            else:
                hours_at_risk = 0

            rain_trigger = total_rain >= cond["rain_mm_trigger"] if cond["rain_mm_trigger"] > 0 else False

            if hours_at_risk >= cond["consecutive_hours"] or rain_trigger:
                risk_pct = min(100, int((hours_at_risk / cond["consecutive_hours"]) * 100))
                alerts.append(DiseaseAlert(
                    disease=disease["name"],
                    pathogen=disease["pathogen"],
                    severity=disease["severity"],
                    risk_percent=risk_pct,
                    hours_favorable=hours_at_risk,
                    affected_crops=[c for c in disease["crops"] if c in user_crops],
                    action=disease["action"],
                    window_starts_in_hrs=max(0, i - hours_at_risk),
                ))
                break

    return sorted(alerts, key=lambda x: -x.risk_percent)


# ═══════════════════════════════════════════════════
#  NEW FEATURE 4: Field Work Windows
# ═══════════════════════════════════════════════════

DRY_DAYS_NEEDED = {
    "harvesting":    {"sandy": 0.5, "loam": 1.0, "clay": 2.0},
    "planting":      {"sandy": 0.5, "loam": 1.5, "clay": 2.5},
    "tillage":       {"sandy": 1.0, "loam": 2.0, "clay": 3.0},
    "spraying":      {"sandy": 0.3, "loam": 0.5, "clay": 1.0},
    "heavy_hauling": {"sandy": 1.0, "loam": 2.5, "clay": 4.0},
}


def compute_field_work_windows(ag_data: dict, soil_type: str = "loam",
                                operation: str = "harvesting") -> list:
    """Compute 7-day field work trafficability windows."""
    daily = ag_data.get("daily", {})
    precip_list = daily.get("precipitation_sum", [])
    temp_max_list = daily.get("temperature_2m_max", [])
    time_list = daily.get("time", [])
    hourly = ag_data.get("hourly", {})
    wind_list = hourly.get("wind_speed_10m", [])

    windows = []
    accumulated_dry_days = 0

    start_idx = max(0, len(precip_list) - 7)

    for i in range(start_idx, min(start_idx + 7, len(precip_list))):
        rain_mm = precip_list[i] if precip_list[i] is not None else 0
        temp_max = temp_max_list[i] if i < len(temp_max_list) and temp_max_list[i] is not None else 15
        date = time_list[i] if i < len(time_list) else f"Day {i - start_idx + 1}"

        frozen = temp_max < 0

        if rain_mm < 2.0:
            accumulated_dry_days += 1.0
        elif rain_mm < 5.0:
            accumulated_dry_days += 0.3
        else:
            accumulated_dry_days = 0

        dry_needed = DRY_DAYS_NEEDED.get(operation, DRY_DAYS_NEEDED["harvesting"]).get(soil_type, 1.0)
        trafficable = accumulated_dry_days >= dry_needed and not frozen

        # Wind check for spraying
        wind_ok = True
        if operation == "spraying" and wind_list:
            day_idx = (i - start_idx) * 24
            day_winds = wind_list[day_idx:day_idx + 24]
            if day_winds:
                avg_wind = sum(w for w in day_winds if w is not None) / max(1, len([w for w in day_winds if w is not None]))
                wind_ok = avg_wind < 15

        rel_idx = i - start_idx
        windows.append(FieldWorkWindow(
            date=date,
            rain_mm=round(rain_mm, 1),
            accumulated_dry_days=round(accumulated_dry_days, 1),
            trafficable=trafficable and wind_ok,
            frozen=frozen,
            compaction_risk="Low" if accumulated_dry_days > dry_needed * 1.5 else "Medium" if trafficable else "High",
            wind_issue=(not wind_ok) if operation == "spraying" else None,
            confidence="High" if rel_idx < 3 else "Moderate" if rel_idx < 5 else "Low",
        ))

    return windows


# ═══════════════════════════════════════════════════
#  NEW FEATURE 5: Harvest Quality Predictor
# ═══════════════════════════════════════════════════

HARVEST_QUALITY_RULES = {
    "corn": {
        "ideal_temp_max": 28, "ideal_humidity_max": 65,
        "rain_sensitivity": "HIGH",
        "quality_risks": {
            "mold": {"humidity_min": 80, "temp_min": 15},
            "aflatoxin": {"humidity_min": 85, "temp_min": 28},
        },
        "moisture_target_pct": 15.5,
    },
    "wheat": {
        "ideal_temp_max": 30, "ideal_humidity_max": 60,
        "rain_sensitivity": "VERY_HIGH",
        "quality_risks": {
            "sprouting": {"rain_mm_3d": 10, "humidity_min": 80},
            "fusarium": {"temp_range": (15, 30), "humidity_min": 85},
        },
        "moisture_target_pct": 13.5,
    },
    "soybeans": {
        "ideal_temp_max": 30, "ideal_humidity_max": 65,
        "rain_sensitivity": "MEDIUM",
        "quality_risks": {
            "mold": {"humidity_min": 85, "temp_min": 20},
            "pod_shatter": {"humidity_fluctuation": 30},
        },
        "moisture_target_pct": 13.0,
    },
    "hay": {
        "ideal_temp_max": 32, "ideal_humidity_max": 55,
        "rain_sensitivity": "VERY_HIGH",
        "quality_risks": {
            "mold": {"rain_mm_any": 2.0},
            "nutrient_loss": {"rain_mm_any": 5.0},
        },
        "moisture_target_pct": 18.0,
    },
}


def compute_harvest_quality(ag_data: dict, crop: str = "corn") -> HarvestQuality:
    """Compute 7-day harvest quality prediction."""
    daily = ag_data.get("daily", {})
    hourly = ag_data.get("hourly", {})

    rules = HARVEST_QUALITY_RULES.get(crop)
    if not rules:
        return HarvestQuality(crop=crop, windows=[], rain_sensitivity="UNKNOWN")

    precip_list = daily.get("precipitation_sum", [])
    temp_max_list = daily.get("temperature_2m_max", [])
    time_list = daily.get("time", [])
    hourly_hum = hourly.get("relative_humidity_2m", [])

    windows = []
    start_idx = max(0, len(precip_list) - 7)
    cumulative_rain_3d = sum(
        (precip_list[j] or 0) for j in range(start_idx, min(start_idx + 3, len(precip_list)))
    )

    for i in range(start_idx, min(start_idx + 7, len(precip_list))):
        rain = precip_list[i] if precip_list[i] is not None else 0
        temp_max = temp_max_list[i] if i < len(temp_max_list) and temp_max_list[i] is not None else 25
        date = time_list[i] if i < len(time_list) else f"Day {i - start_idx + 1}"

        # Get hourly humidity for this day
        day_offset = (i - start_idx) * 24
        day_humidity = hourly_hum[day_offset:day_offset + 24]
        valid_hum = [h for h in day_humidity if h is not None]
        avg_humidity = sum(valid_hum) / len(valid_hum) if valid_hum else 70
        humidity_swing = (max(valid_hum) - min(valid_hum)) if len(valid_hum) >= 2 else 0

        quality_score = 100
        risks_flagged = []

        if rain > 0.5:
            deduction = min(50, rain * 8)
            quality_score -= deduction
            risks_flagged.append(f"Rain ({rain}mm) — harvesting delays likely")

        if avg_humidity > rules["ideal_humidity_max"]:
            quality_score -= (avg_humidity - rules["ideal_humidity_max"]) * 0.8
            risks_flagged.append(f"High humidity ({avg_humidity:.0f}%) — drying costs increase")

        if temp_max > rules["ideal_temp_max"] and avg_humidity > 75:
            quality_score -= 15
            risks_flagged.append("Heat + humidity combo — mold risk elevated")

        # Crop-specific risks
        crop_risks = rules.get("quality_risks", {})
        if "sprouting" in crop_risks and cumulative_rain_3d > crop_risks["sprouting"].get("rain_mm_3d", 999):
            quality_score -= 20
            risks_flagged.append("⚠️ Sprouting risk — 3-day cumulative rain threshold exceeded")

        if "pod_shatter" in crop_risks and humidity_swing > crop_risks["pod_shatter"].get("humidity_fluctuation", 999):
            quality_score -= 10
            risks_flagged.append("Pod shatter risk — large humidity swings detected")

        quality_score = max(0, round(quality_score))
        grade = ("A — Ideal" if quality_score >= 85 else
                 "B — Good" if quality_score >= 70 else
                 "C — Marginal" if quality_score >= 50 else
                 "D — Poor — Consider waiting")

        windows.append(HarvestDay(
            date=date,
            quality_score=quality_score,
            grade=grade,
            rain_mm=round(rain, 1),
            avg_humidity_pct=round(avg_humidity, 1),
            risks=risks_flagged,
            harvest_recommended=quality_score >= 70 and rain < 2.0,
        ))

    best_window = max(windows, key=lambda x: x.quality_score) if windows else None

    return HarvestQuality(
        crop=crop,
        moisture_target_pct=rules["moisture_target_pct"],
        windows=windows,
        best_harvest_day=best_window,
        rain_sensitivity=rules["rain_sensitivity"],
    )
