I'd tackle Health & Wellness features, and then step-by-step instructions for each:

**Impact order:** SAD Index → Medication Storage Alerts → Air Quality Composite → Outdoor Exercise Window → Hydration Estimator → Sunscreen/UV Plan → Heart/Stroke Risk → Respiratory indices

---

## 1. 🧠 SAD Index (Seasonal Affective Disorder)

**Why first:** Mental health + weather is a gap no mainstream app fills well. High emotional value, drives retention.

**Data you need** (all from Open-Meteo, free):
- `sunshine_duration` (hourly) — seconds of sunshine per hour
- `daylight_duration` (daily) — total daylight seconds
- `cloudcover` (hourly)
- Historical 30-day rolling averages of both

**Step-by-step:**

**Step 1 — Fetch the data in your FastAPI backend**
```python
# Open-Meteo endpoint additions
params = {
    "latitude": lat,
    "longitude": lon,
    "hourly": ["sunshine_duration", "cloudcover"],
    "daily": ["daylight_duration", "sunshine_duration"],
    "past_days": 30,  # rolling 30-day window
    "timezone": "auto"
}
```

**Step 2 — Compute the SAD Index score (0–100)**
```python
def compute_sad_index(daily_data: dict) -> dict:
    """
    Clinical threshold: <2 hrs sunshine/day for 2+ weeks = SAD risk zone
    Score 0 = no risk, 100 = severe risk
    """
    sunshine_hours = [s / 3600 for s in daily_data["sunshine_duration"]]  # seconds → hours
    daylight_hours = [d / 3600 for d in daily_data["daylight_duration"]]

    last_14 = sunshine_hours[-14:]
    avg_sunshine = sum(last_14) / len(last_14)

    # Deficit ratio: how far below 2hr clinical threshold
    deficit_ratio = max(0, (2.0 - avg_sunshine) / 2.0)

    # Consecutive low-sun days (below 1hr) amplifies score
    consecutive_low = sum(1 for h in last_14 if h < 1.0)
    streak_penalty = min(consecutive_low * 4, 30)  # caps at 30 pts

    raw_score = (deficit_ratio * 70) + streak_penalty
    score = min(round(raw_score), 100)

    # Light therapy window: find tomorrow's best 2hr sunshine window
    today_sunshine = sunshine_hours[-1]

    return {
        "sad_index": score,
        "avg_sunshine_hrs_14d": round(avg_sunshine, 2),
        "consecutive_low_sun_days": consecutive_low,
        "risk_level": "High" if score > 65 else "Moderate" if score > 35 else "Low",
        "recommendation": _sad_recommendation(score, avg_sunshine)
    }

def _sad_recommendation(score: int, avg_sun: float) -> str:
    if score > 65:
        return "Consider a 10,000 lux light therapy lamp — 20–30 min each morning. Consult a doctor if symptoms persist."
    elif score > 35:
        return f"You're averaging {avg_sun:.1f} hrs of sun/day. Prioritize outdoor time during midday when possible."
    return "Sunlight exposure is adequate. Maintain outdoor habits."
```

**Step 3 — Add FastAPI route**
```python
@app.get("/health/sad-index")
def sad_index(lat: float, lon: float):
    raw = fetch_openmeteo(lat, lon, past_days=30)
    return compute_sad_index(raw["daily"])
```

**Step 4 — Streamlit UI**
```python
sad = requests.get(f"{API}/health/sad-index", params={"lat": lat, "lon": lon}).json()

col1, col2 = st.columns([1, 2])
with col1:
    # Color-coded gauge
    color = "🔴" if sad["risk_level"] == "High" else "🟡" if sad["risk_level"] == "Moderate" else "🟢"
    st.metric(f"{color} SAD Index", sad["sad_index"], help="0=No risk, 100=High risk")
    st.caption(f"Avg sunshine last 14 days: {sad['avg_sunshine_hrs_14d']} hrs/day")
with col2:
    st.info(f"💡 {sad['recommendation']}")
```

**Step 5 — Plug into your existing LLM RAG**
Add SAD index score to your RAG context so the AI chatbot can answer "why do I feel low lately?" with actual sunlight data behind it.

---

## 2. 💊 Medication Storage Alerts

**Why second:** Life-critical, genuinely novel, zero competition in weather apps. Insulin users alone are millions of people.

**Data needed:**
- Current `temperature_2m` (already have this)
- `relative_humidity_2m`
- 24-hr forecast of both

**Step 1 — Build a medication rules database**
```python
# No ML needed — pure rules from FDA/manufacturer guidelines
MEDICATION_RULES = {
    "insulin": {
        "temp_min_c": 2, "temp_max_c": 30,
        "humidity_max": 80,
        "note": "Opened vials: room temp OK up to 30°C for 28 days. Unopened: refrigerate."
    },
    "epinephrine": {
        "temp_min_c": 15, "temp_max_c": 25,
        "humidity_max": 75,
        "note": "EpiPen degrades above 25°C. Never leave in a hot car."
    },
    "nitroglycerin": {
        "temp_min_c": 15, "temp_max_c": 25,
        "humidity_max": 70,
        "note": "Extremely heat and moisture sensitive. Keep in original container."
    },
    "inhaler": {
        "temp_min_c": 15, "temp_max_c": 30,
        "humidity_max": 85,
        "note": "Cold reduces propellant effectiveness. Heat can cause canister to burst."
    },
    "thyroid_medication": {
        "temp_min_c": 15, "temp_max_c": 25,
        "humidity_max": 60,
        "note": "Highly humidity-sensitive. Keep in airtight container."
    }
}
```

**Step 2 — Alert logic**
```python
def check_medication_alerts(weather: dict, user_meds: list[str]) -> list[dict]:
    temp = weather["current"]["temperature_2m"]
    humidity = weather["current"]["relative_humidity_2m"]
    
    # Also check next 6 hours from forecast
    forecast_temps = weather["hourly"]["temperature_2m"][:6]
    max_forecast_temp = max(forecast_temps)
    
    alerts = []
    for med in user_meds:
        if med not in MEDICATION_RULES:
            continue
        rule = MEDICATION_RULES[med]
        issues = []

        check_temp = max(temp, max_forecast_temp)  # worst case
        if check_temp > rule["temp_max_c"]:
            issues.append(f"Temperature ({check_temp:.1f}°C) exceeds safe storage limit of {rule['temp_max_c']}°C")
        if check_temp < rule["temp_min_c"]:
            issues.append(f"Temperature ({check_temp:.1f}°C) is below safe minimum of {rule['temp_min_c']}°C")
        if humidity > rule["humidity_max"]:
            issues.append(f"Humidity ({humidity}%) exceeds safe limit of {rule['humidity_max']}%")

        if issues:
            alerts.append({
                "medication": med,
                "severity": "HIGH" if len(issues) > 1 else "MODERATE",
                "issues": issues,
                "note": rule["note"]
            })

    return alerts
```

**Step 3 — FastAPI route with user preferences**
```python
@app.get("/health/medication-alerts")
def medication_alerts(lat: float, lon: float, medications: str):
    # medications passed as comma-separated: "insulin,epinephrine"
    med_list = [m.strip() for m in medications.split(",")]
    weather = fetch_openmeteo(lat, lon)
    return {"alerts": check_medication_alerts(weather, med_list)}
```

**Step 4 — Streamlit UI with med selector**
```python
st.subheader("💊 Medication Storage Monitor")
user_meds = st.multiselect(
    "Select your medications",
    options=list(MEDICATION_RULES.keys()),
    format_func=lambda x: x.replace("_", " ").title()
)

if user_meds:
    result = requests.get(f"{API}/health/medication-alerts",
        params={"lat": lat, "lon": lon, "medications": ",".join(user_meds)}).json()
    
    if not result["alerts"]:
        st.success("✅ Current conditions are safe for all your medications.")
    for alert in result["alerts"]:
        severity_icon = "🚨" if alert["severity"] == "HIGH" else "⚠️"
        with st.expander(f"{severity_icon} {alert['medication'].replace('_',' ').title()} Alert"):
            for issue in alert["issues"]:
                st.write(f"• {issue}")
            st.caption(alert["note"])
```

**Step 5 — Persist med preferences**
Store user medication selections in `st.session_state` or a simple local JSON so they don't re-select every visit.

---

## 3. 🌬️ Air Quality Composite Score

**Data needed:** Open-Meteo Air Quality API (free) — `pm2_5`, `pm10`, `ozone`, `nitrogen_dioxide`, `us_aqi`

**Step 1 — Fetch AQ data (separate Open-Meteo endpoint)**
```python
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

def fetch_air_quality(lat, lon):
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["pm2_5", "pm10", "ozone", "nitrogen_dioxide", "us_aqi"],
        "timezone": "auto", "forecast_days": 3
    }
    return requests.get(AQ_URL, params=params).json()
```

**Step 2 — Composite score + activity tiers**
```python
def compute_aq_composite(aq_data: dict) -> dict:
    current_hour = datetime.now().hour
    aqi = aq_data["hourly"]["us_aqi"][current_hour]
    pm25 = aq_data["hourly"]["pm2_5"][current_hour]

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

    return {
        "us_aqi": aqi, "pm2_5": pm25,
        "icon": icon, "tier": tier,
        "activity_guidance": activities,
        "worst_pollutant": "PM2.5" if pm25 > 35 else "Ozone" if aqi > 100 else "None"
    }
```

**Step 3 — FastAPI + Streamlit** — same pattern as above, just render activity guidance as a checklist in the UI.

---

## 4. 🏃 Outdoor Exercise Window

**Why it's impactful:** "When should I go for a run today?" is a question millions ask daily. No app answers it well.

**Step 1 — Score each hour (0–100, higher = better)**
```python
def score_exercise_windows(hourly: dict, date: str) -> list[dict]:
    windows = []
    hours = [i for i, t in enumerate(hourly["time"]) if t.startswith(date)]

    for i in hours:
        temp = hourly["temperature_2m"][i]
        humidity = hourly["relative_humidity_2m"][i]
        uv = hourly.get("uv_index", [0]*24)[i]
        precip_prob = hourly["precipitation_probability"][i]
        aqi = hourly.get("us_aqi", [50]*24)[i]  # from AQ API

        # Score each factor (higher = better)
        temp_score = 100 - abs(temp - 18) * 4      # ideal ~18°C
        humidity_score = max(0, 100 - humidity)     # lower humidity better
        uv_score = max(0, 100 - uv * 10)            # UV<3 ideal
        rain_score = max(0, 100 - precip_prob)
        aqi_score = max(0, 100 - aqi)

        composite = (
            temp_score * 0.30 +
            humidity_score * 0.20 +
            uv_score * 0.20 +
            rain_score * 0.20 +
            aqi_score * 0.10
        )
        windows.append({
            "hour": i,
            "time_label": f"{i:02d}:00",
            "score": round(composite),
            "temp_c": temp,
            "uv_index": uv,
            "precip_prob": precip_prob
        })

    # Return top 3 windows
    return sorted(windows, key=lambda x: -x["score"])[:3]
```

**Step 2 — UI:** Show as a ranked card list — "🥇 6:00 AM — Score 87 | 17°C, UV 1, 5% rain chance"

---

## 5. 💧 Hydration Estimator

**No external API needed** — pure formula from sports medicine research.

```python
def compute_hydration(temp_c: float, humidity: float,
                       activity: str, weight_kg: float) -> dict:
    # Base: 35ml per kg body weight
    base_ml = weight_kg * 35

    # Heat adjustment (adds up to 750ml in extreme heat)
    heat_factor = max(0, (temp_c - 20) * 30)

    # Humidity adjustment (high humidity reduces sweat evaporation = more strain)
    humidity_factor = max(0, (humidity - 50) * 5)

    # Activity multipliers
    activity_factors = {
        "sedentary": 1.0, "light_walk": 1.2,
        "moderate_exercise": 1.5, "intense_exercise": 1.8
    }
    activity_mul = activity_factors.get(activity, 1.0)

    total_ml = (base_ml + heat_factor + humidity_factor) * activity_mul
    cups = round(total_ml / 240)

    return {
        "total_ml": round(total_ml),
        "cups_8oz": cups,
        "tip": "Drink 500ml 2 hrs before going outside on hot days" if temp_c > 28 else "Sip regularly — don't wait until thirsty"
    }
```

**Streamlit UI:** Add a sidebar widget with weight input + activity dropdown. Updates live as weather changes.

---

These 5 cover crops, livestock, and field operations, so you'll serve all user types. Here's the impact-first order:

**Order:** Irrigation Scheduler → Livestock Heat Stress → Crop Disease Calendar → Field Work Windows → Harvest Quality Predictor

---

## 1. 💧 Irrigation Scheduler

**Why first:** Water management is the #1 daily decision for every farmer. Saves money, saves crops, universal appeal.

**Core concept:** Irrigation need = Crop water demand (ET) − Effective rainfall. Open-Meteo gives you both.

**Step 1 — Fetch the right Open-Meteo variables**
```python
def fetch_agriculture_data(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m", 
            "wind_speed_10m",
            "shortwave_radiation",      # solar radiation for ET calc
            "precipitation",
            "et0_fao_evapotranspiration" # Open-Meteo gives this directly!
        ],
        "daily": [
            "et0_fao_evapotranspiration",  # daily ET reference
            "precipitation_sum",
            "temperature_2m_max",
            "temperature_2m_min",
            "rain_sum"
        ],
        "past_days": 7,
        "forecast_days": 7,
        "timezone": "auto"
    }
    return requests.get("https://api.open-meteo.com/v1/forecast", params=params).json()
```

**Step 2 — Crop coefficient table (Kc values from FAO-56 standard)**
```python
# Kc multiplied by ET0 gives actual crop water need
# Values: (Kc_initial, Kc_mid, Kc_late)
CROP_KC = {
    "corn":         {"initial": 0.3, "mid": 1.20, "late": 0.35, "root_depth_m": 1.0},
    "wheat":        {"initial": 0.3, "mid": 1.15, "late": 0.25, "root_depth_m": 1.0},
    "soybeans":     {"initial": 0.4, "mid": 1.15, "late": 0.50, "root_depth_m": 0.9},
    "tomatoes":     {"initial": 0.6, "mid": 1.15, "late": 0.70, "root_depth_m": 0.7},
    "potatoes":     {"initial": 0.5, "mid": 1.15, "late": 0.65, "root_depth_m": 0.5},
    "cotton":       {"initial": 0.35,"mid": 1.20, "late": 0.50, "root_depth_m": 1.0},
    "grass/pasture":{"initial": 0.9, "mid": 1.00, "late": 1.00, "root_depth_m": 0.3},
    "vegetables":   {"initial": 0.5, "mid": 1.00, "late": 0.80, "root_depth_m": 0.4},
}
```

**Step 3 — Core irrigation calculator**
```python
def compute_irrigation_schedule(
    ag_data: dict,
    crop: str,
    growth_stage: str,          # "initial", "mid", "late"
    soil_type: str = "loam",    # affects water holding capacity
    area_hectares: float = 1.0
) -> dict:

    # Soil water holding capacity (mm per meter of root depth)
    SOIL_WHC = {
        "sandy": 100, "sandy_loam": 130, "loam": 170,
        "clay_loam": 190, "clay": 200
    }

    kc = CROP_KC[crop][growth_stage]
    root_depth = CROP_KC[crop]["root_depth_m"]
    whc = SOIL_WHC[soil_type]

    daily = ag_data["daily"]
    schedule = []

    # Track soil moisture balance (start at 70% field capacity)
    soil_moisture_mm = whc * root_depth * 0.70
    field_capacity = whc * root_depth
    # Irrigate when soil drops to 50% (MAD - Management Allowed Depletion)
    mad_threshold = field_capacity * 0.50

    for i in range(7):  # 7-day forecast
        et0 = daily["et0_fao_evapotranspiration"][i]
        etc = et0 * kc                          # actual crop ET
        rain = daily["rain_sum"][i]
        effective_rain = rain * 0.75            # ~75% of rain is effective

        # Update soil moisture
        soil_moisture_mm = soil_moisture_mm - etc + effective_rain
        soil_moisture_mm = min(soil_moisture_mm, field_capacity)  # cap at field capacity

        irrigate = soil_moisture_mm < mad_threshold
        deficit_mm = max(0, field_capacity - soil_moisture_mm)

        # Convert mm to liters for the area
        water_liters = deficit_mm * area_hectares * 10000 / 1000  # mm→liters/ha→total

        schedule.append({
            "date": daily["time"][i],
            "et0_mm": round(et0, 2),
            "crop_water_need_mm": round(etc, 2),
            "effective_rain_mm": round(effective_rain, 2),
            "soil_moisture_pct": round((soil_moisture_mm / field_capacity) * 100, 1),
            "irrigate_today": irrigate,
            "deficit_mm": round(deficit_mm, 2),
            "water_needed_liters": round(water_liters) if irrigate else 0
        })

    # Find next irrigation day
    next_irrigation = next((d for d in schedule if d["irrigate_today"]), None)

    return {
        "crop": crop,
        "growth_stage": growth_stage,
        "area_hectares": area_hectares,
        "schedule": schedule,
        "next_irrigation": next_irrigation,
        "weekly_water_need_mm": round(sum(d["crop_water_need_mm"] for d in schedule), 1)
    }
```

**Step 4 — FastAPI route**
```python
@app.get("/agriculture/irrigation")
def irrigation_schedule(
    lat: float, lon: float,
    crop: str = "corn",
    growth_stage: str = "mid",
    soil_type: str = "loam",
    area_hectares: float = 1.0
):
    ag_data = fetch_agriculture_data(lat, lon)
    return compute_irrigation_schedule(ag_data, crop, growth_stage, soil_type, area_hectares)
```

**Step 5 — Streamlit UI**
```python
st.subheader("💧 Irrigation Scheduler")

col1, col2, col3, col4 = st.columns(4)
with col1:
    crop = st.selectbox("Crop", list(CROP_KC.keys()))
with col2:
    stage = st.selectbox("Growth Stage", ["initial", "mid", "late"])
with col3:
    soil = st.selectbox("Soil Type", ["sandy", "sandy_loam", "loam", "clay_loam", "clay"])
with col4:
    area = st.number_input("Area (hectares)", min_value=0.1, value=1.0, step=0.5)

result = requests.get(f"{API}/agriculture/irrigation", params={
    "lat": lat, "lon": lon, "crop": crop,
    "growth_stage": stage, "soil_type": soil, "area_hectares": area
}).json()

# Next irrigation alert
if result["next_irrigation"]:
    nxt = result["next_irrigation"]
    st.warning(f"🚿 Next irrigation: **{nxt['date']}** — {nxt['deficit_mm']}mm deficit "
               f"({nxt['water_needed_liters']:,} liters)")
else:
    st.success("✅ No irrigation needed this week — soil moisture is adequate.")

# 7-day table
import pandas as pd
df = pd.DataFrame(result["schedule"])
df["irrigate_today"] = df["irrigate_today"].map({True: "🚿 Yes", False: "✅ No"})
st.dataframe(df[["date","crop_water_need_mm","effective_rain_mm",
                  "soil_moisture_pct","irrigate_today","water_needed_liters"]],
             use_container_width=True)
```

---

## 2. 🐄 Livestock Heat Stress Index (THI)

**Why second:** A single hot day can kill poultry flocks or drop dairy production 20%. Livestock farmers check this daily.

**Core concept:** Temperature-Humidity Index (THI) — the industry standard metric used by USDA and every dairy co-op.

**Step 1 — THI formula by species**
```python
def compute_thi(temp_c: float, humidity: float) -> float:
    """Standard THI formula used by USDA"""
    temp_f = (temp_c * 9/5) + 32
    return (0.8 * temp_f) + ((humidity / 100) * (temp_f - 14.4)) + 46.4

SPECIES_THRESHOLDS = {
    "dairy_cattle": {
        "comfortable":  {"max": 68,  "label": "✅ Comfortable", "color": "green"},
        "alert":        {"max": 72,  "label": "⚠️ Alert",       "color": "yellow"},
        "danger":       {"max": 80,  "label": "🟠 Danger",      "color": "orange"},
        "emergency":    {"max": 999, "label": "🔴 Emergency",   "color": "red"},
        "impacts": {
            "alert":     "Milk production drops 10–15%",
            "danger":    "Milk drops 25%+, conception rates fall",
            "emergency": "Risk of death. Immediate intervention required"
        }
    },
    "beef_cattle": {
        "comfortable":  {"max": 70,  "label": "✅ Comfortable", "color": "green"},
        "alert":        {"max": 74,  "label": "⚠️ Alert",       "color": "yellow"},
        "danger":       {"max": 79,  "label": "🟠 Danger",      "color": "orange"},
        "emergency":    {"max": 999, "label": "🔴 Emergency",   "color": "red"},
    },
    "poultry": {
        "comfortable":  {"max": 70,  "label": "✅ Comfortable", "color": "green"},
        "alert":        {"max": 75,  "label": "⚠️ Alert",       "color": "yellow"},
        "danger":       {"max": 80,  "label": "🟠 Danger",      "color": "orange"},
        "emergency":    {"max": 999, "label": "🔴 Emergency",   "color": "red"},
        "impacts": {
            "alert":     "Feed intake drops, egg production falls",
            "danger":    "Panting, reduced egg weight, mortality risk rises",
            "emergency": "Mass mortality possible within hours"
        }
    },
    "swine": {
        "comfortable":  {"max": 74,  "label": "✅ Comfortable", "color": "green"},
        "alert":        {"max": 78,  "label": "⚠️ Alert",       "color": "yellow"},
        "danger":       {"max": 84,  "label": "🟠 Danger",      "color": "orange"},
        "emergency":    {"max": 999, "label": "🔴 Emergency",   "color": "red"},
    }
}

def classify_thi(thi: float, species: str) -> dict:
    thresholds = SPECIES_THRESHOLDS[species]
    for level in ["comfortable", "alert", "danger", "emergency"]:
        if thi <= thresholds[level]["max"]:
            impacts = thresholds.get("impacts", {})
            return {
                "level": level,
                "label": thresholds[level]["label"],
                "impact": impacts.get(level, "Monitor conditions")
            }
```

**Step 2 — Full analysis with hourly forecast**
```python
def compute_livestock_heat_stress(ag_data: dict, species: str) -> dict:
    hourly = ag_data["hourly"]
    results = []

    for i in range(48):  # 48-hour window
        temp = hourly["temperature_2m"][i]
        humidity = hourly["relative_humidity_2m"][i]
        thi = compute_thi(temp, humidity)
        classification = classify_thi(thi, species)

        results.append({
            "time": hourly["time"][i],
            "temp_c": temp,
            "humidity_pct": humidity,
            "thi": round(thi, 1),
            **classification
        })

    # Peak stress period
    peak = max(results, key=lambda x: x["thi"])
    danger_hours = [r for r in results if r["level"] in ["danger", "emergency"]]

    # Mitigation advice
    mitigations = _get_mitigation_advice(peak["level"], species)

    return {
        "species": species,
        "current_thi": results[0]["thi"],
        "current_level": results[0]["label"],
        "peak_thi": peak["thi"],
        "peak_time": peak["time"],
        "danger_hours_count": len(danger_hours),
        "hourly_forecast": results[:24],
        "mitigations": mitigations
    }

def _get_mitigation_advice(level: str, species: str) -> list[str]:
    base = {
        "alert": [
            "Ensure continuous access to fresh, cool water",
            "Increase ventilation in barns/sheds",
            "Schedule feeding during cooler morning/evening hours"
        ],
        "danger": [
            "Activate all fans and evaporative cooling systems",
            "Add electrolytes to drinking water",
            "Reduce stocking density if possible",
            "Delay any transportation or handling"
        ],
        "emergency": [
            "🚨 Emergency cooling required immediately",
            "Spray animals with cool water every 30 minutes",
            "Contact your veterinarian",
            "Move animals to shaded/air-conditioned areas",
            "Do NOT move or handle animals unless necessary"
        ]
    }
    return base.get(level, ["Conditions are comfortable — routine monitoring"])
```

**Step 3 — FastAPI + Streamlit**
```python
# FastAPI
@app.get("/agriculture/livestock-heat-stress")
def livestock_heat_stress(lat: float, lon: float, species: str = "dairy_cattle"):
    ag_data = fetch_agriculture_data(lat, lon)
    return compute_livestock_heat_stress(ag_data, species)

# Streamlit
st.subheader("🐄 Livestock Heat Stress Monitor")
species = st.selectbox("Livestock Type",
    ["dairy_cattle", "beef_cattle", "poultry", "swine"],
    format_func=lambda x: x.replace("_", " ").title())

result = requests.get(f"{API}/agriculture/livestock-heat-stress",
    params={"lat": lat, "lon": lon, "species": species}).json()

col1, col2, col3 = st.columns(3)
col1.metric("Current THI", result["current_thi"], help="<68 safe for dairy cattle")
col2.metric("Status", result["current_level"])
col3.metric("Peak THI (24hr)", result["peak_thi"], f"at {result['peak_time'][11:16]}")

if result["danger_hours_count"] > 0:
    st.error(f"⚠️ {result['danger_hours_count']} danger-level hours forecast in next 24hrs")

st.subheader("Recommended Actions")
for action in result["mitigations"]:
    st.write(f"• {action}")
```

---

## 3. 🦠 Crop Disease Calendar

**Why third:** A single blight outbreak can wipe an entire season. Farmers check this anxiously during wet/humid stretches.

**Core concept:** Each disease has a specific temperature + humidity + leaf wetness window. Match weather to that window.

**Step 1 — Disease rules database**
```python
# Based on published plant pathology research
DISEASE_RULES = {
    "late_blight_tomato": {
        "name": "Late Blight (Tomato/Potato)",
        "crops": ["tomatoes", "potatoes"],
        "conditions": {
            "temp_min_c": 10, "temp_max_c": 24,
            "humidity_min": 90,
            "consecutive_hours": 10,     # hours of high humidity needed
            "rain_mm_trigger": 2.0       # or rainfall trigger
        },
        "severity": "HIGH",
        "action": "Apply fungicide within 24hrs. Remove infected leaves immediately.",
        "pathogen": "Phytophthora infestans"
    },
    "gray_mold": {
        "name": "Gray Mold (Botrytis)",
        "crops": ["tomatoes", "strawberries", "grapes", "vegetables"],
        "conditions": {
            "temp_min_c": 15, "temp_max_c": 25,
            "humidity_min": 85,
            "consecutive_hours": 8,
            "rain_mm_trigger": 1.0
        },
        "severity": "HIGH",
        "action": "Improve air circulation. Apply fungicide. Remove dead plant material.",
        "pathogen": "Botrytis cinerea"
    },
    "corn_blight": {
        "name": "Northern Corn Leaf Blight",
        "crops": ["corn"],
        "conditions": {
            "temp_min_c": 18, "temp_max_c": 27,
            "humidity_min": 80,
            "consecutive_hours": 12,
            "rain_mm_trigger": 5.0
        },
        "severity": "MEDIUM",
        "action": "Scout fields. Consider fungicide at tasseling if >50% plants infected.",
        "pathogen": "Exserohilum turcicum"
    },
    "powdery_mildew": {
        "name": "Powdery Mildew",
        "crops": ["wheat", "grapes", "vegetables", "soybeans"],
        "conditions": {
            "temp_min_c": 15, "temp_max_c": 28,
            "humidity_min": 70,         # unlike others, doesn't need very high humidity
            "consecutive_hours": 6,
            "rain_mm_trigger": 0        # actually LESS rain favors this
        },
        "severity": "MEDIUM",
        "action": "Apply sulfur-based fungicide. Avoid overhead irrigation.",
        "pathogen": "Various Erysiphe species"
    },
    "wheat_rust": {
        "name": "Wheat Rust",
        "crops": ["wheat"],
        "conditions": {
            "temp_min_c": 15, "temp_max_c": 22,
            "humidity_min": 95,
            "consecutive_hours": 6,
            "rain_mm_trigger": 1.0
        },
        "severity": "HIGH",
        "action": "Apply fungicide immediately. Report to local extension office.",
        "pathogen": "Puccinia spp."
    },
    "soybean_sclerotinia": {
        "name": "White Mold (Sclerotinia)",
        "crops": ["soybeans"],
        "conditions": {
            "temp_min_c": 15, "temp_max_c": 25,
            "humidity_min": 85,
            "consecutive_hours": 10,
            "rain_mm_trigger": 3.0
        },
        "severity": "HIGH",
        "action": "Apply fungicide at early flowering. Improve field drainage.",
        "pathogen": "Sclerotinia sclerotiorum"
    }
}
```

**Step 2 — Risk detection engine**
```python
def compute_disease_risk(ag_data: dict, user_crops: list[str]) -> list[dict]:
    hourly = ag_data["hourly"]
    alerts = []

    for disease_key, disease in DISEASE_RULES.items():
        # Skip if not relevant to user's crops
        if not any(c in disease["crops"] for c in user_crops):
            continue

        cond = disease["conditions"]
        hours_at_risk = 0
        total_rain = 0

        # Scan next 72 hours
        for i in range(72):
            temp = hourly["temperature_2m"][i]
            humidity = hourly["relative_humidity_2m"][i]
            rain = hourly["precipitation"][i]

            total_rain += rain
            in_temp_range = cond["temp_min_c"] <= temp <= cond["temp_max_c"]
            in_humidity_range = humidity >= cond["humidity_min"]

            if in_temp_range and in_humidity_range:
                hours_at_risk += 1
            else:
                hours_at_risk = 0  # reset — needs CONSECUTIVE hours

            # Trigger if consecutive hours exceeded OR rain threshold met
            rain_trigger = total_rain >= cond["rain_mm_trigger"] if cond["rain_mm_trigger"] > 0 else False

            if hours_at_risk >= cond["consecutive_hours"] or rain_trigger:
                risk_pct = min(100, int((hours_at_risk / cond["consecutive_hours"]) * 100))
                alerts.append({
                    "disease": disease["name"],
                    "pathogen": disease["pathogen"],
                    "severity": disease["severity"],
                    "risk_percent": risk_pct,
                    "hours_favorable": hours_at_risk,
                    "affected_crops": [c for c in disease["crops"] if c in user_crops],
                    "action": disease["action"],
                    "window_starts_in_hrs": i - hours_at_risk
                })
                break  # one alert per disease per forecast

    return sorted(alerts, key=lambda x: -x["risk_percent"])
```

**Step 3 — FastAPI + Streamlit**
```python
# FastAPI
@app.get("/agriculture/disease-risk")
def disease_risk(lat: float, lon: float, crops: str):
    crop_list = [c.strip() for c in crops.split(",")]
    ag_data = fetch_agriculture_data(lat, lon)
    return {"alerts": compute_disease_risk(ag_data, crop_list)}

# Streamlit
st.subheader("🦠 Crop Disease Calendar")
user_crops = st.multiselect("Your crops", 
    ["corn","wheat","soybeans","tomatoes","potatoes","grapes","vegetables"])

if user_crops:
    result = requests.get(f"{API}/agriculture/disease-risk",
        params={"lat": lat, "lon": lon, "crops": ",".join(user_crops)}).json()

    if not result["alerts"]:
        st.success("✅ No disease risk detected in the next 72 hours for your crops.")
    
    for alert in result["alerts"]:
        severity_color = "🔴" if alert["severity"] == "HIGH" else "🟡"
        with st.expander(f"{severity_color} {alert['disease']} — Risk: {alert['risk_percent']}%"):
            st.write(f"**Pathogen:** {alert['pathogen']}")
            st.write(f"**Affects:** {', '.join(alert['affected_crops'])}")
            st.write(f"**Favorable conditions start in:** ~{alert['window_starts_in_hrs']} hours")
            st.warning(f"**Action:** {alert['action']}")
```

---

## 4. 🚜 Field Work Windows

**Why fourth:** Soil compaction from wet-field operations is a permanent yield loss. Farmers lose thousands by misjudging this.

**Step 1 — Soil trafficability model**
```python
def compute_field_work_windows(ag_data: dict, soil_type: str, 
                                operation: str) -> list[dict]:
    # Minimum dry days needed before field work by operation + soil type
    DRY_DAYS_NEEDED = {
        "harvesting":   {"sandy": 0.5, "loam": 1.0, "clay": 2.0},
        "planting":     {"sandy": 0.5, "loam": 1.5, "clay": 2.5},
        "tillage":      {"sandy": 1.0, "loam": 2.0, "clay": 3.0},
        "spraying":     {"sandy": 0.3, "loam": 0.5, "clay": 1.0},
        "heavy_hauling":{"sandy": 1.0, "loam": 2.5, "clay": 4.0}
    }

    daily = ag_data["daily"]
    windows = []
    accumulated_dry_days = 0

    for i in range(7):
        rain_mm = daily["precipitation_sum"][i]
        temp_max = daily["temperature_2m_max"][i]
        temp_min = daily["temperature_2m_min"][i]

        # Frozen ground = no work (but also no compaction risk)
        frozen = temp_max < 0

        # Accumulate dry time
        if rain_mm < 2.0:   # <2mm counts as a dry day
            accumulated_dry_days += 1.0
        elif rain_mm < 5.0:
            accumulated_dry_days += 0.3   # partial recovery
        else:
            accumulated_dry_days = 0      # reset after significant rain

        dry_needed = DRY_DAYS_NEEDED[operation][soil_type]
        trafficable = accumulated_dry_days >= dry_needed and not frozen

        # Wind check for spraying
        wind_ok = True
        if operation == "spraying":
            avg_wind = sum(ag_data["hourly"]["wind_speed_10m"][i*24:(i+1)*24]) / 24
            wind_ok = avg_wind < 15  # km/h limit for spray drift

        windows.append({
            "date": daily["time"][i],
            "rain_mm": round(rain_mm, 1),
            "accumulated_dry_days": round(accumulated_dry_days, 1),
            "trafficable": trafficable and wind_ok,
            "frozen": frozen,
            "compaction_risk": "Low" if accumulated_dry_days > dry_needed * 1.5
                               else "Medium" if trafficable else "High",
            "wind_issue": not wind_ok if operation == "spraying" else None,
            "confidence": "High" if i < 3 else "Moderate" if i < 5 else "Low"
        })

    return windows
```

**Step 2 — FastAPI + Streamlit**
```python
# FastAPI
@app.get("/agriculture/field-windows")
def field_windows(lat: float, lon: float, 
                  soil_type: str = "loam", operation: str = "harvesting"):
    ag_data = fetch_agriculture_data(lat, lon)
    windows = compute_field_work_windows(ag_data, soil_type, operation)
    best_day = next((w for w in windows if w["trafficable"]), None)
    return {"windows": windows, "next_workable_day": best_day}

# Streamlit
st.subheader("🚜 Field Work Windows")
col1, col2 = st.columns(2)
with col1:
    operation = st.selectbox("Operation Type",
        ["harvesting", "planting", "tillage", "spraying", "heavy_hauling"],
        format_func=lambda x: x.replace("_", " ").title())
with col2:
    soil = st.selectbox("Soil Type", ["sandy", "loam", "clay"])

result = requests.get(f"{API}/agriculture/field-windows",
    params={"lat": lat, "lon": lon, "soil_type": soil, "operation": operation}).json()

if result["next_workable_day"]:
    st.success(f"✅ Next workable day: **{result['next_workable_day']['date']}**")
else:
    st.error("🚫 No workable days in the next 7 days — too wet or conditions unfavorable")

# Calendar-style display
for w in result["windows"]:
    icon = "✅" if w["trafficable"] else ("❄️" if w["frozen"] else "🚫")
    risk_color = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
    st.write(f"{icon} **{w['date']}** — Rain: {w['rain_mm']}mm | "
             f"Compaction Risk: {risk_color[w['compaction_risk']]} {w['compaction_risk']} | "
             f"Forecast confidence: {w['confidence']}")
```

---

## 5. 🌾 Harvest Quality Predictor

**Why last of five:** Highest value for grain/fruit farmers but narrower audience than the others.

**Core concept:** Rain during harvest = downgraded grain (mold, sprouting), delayed ops, dockage fees. Predict the optimal harvest window.

**Step 1 — Crop-specific harvest quality rules**
```python
HARVEST_QUALITY_RULES = {
    "corn": {
        "ideal_temp_max": 28, "ideal_humidity_max": 65,
        "rain_sensitivity": "HIGH",
        "quality_risks": {
            "mold": {"humidity_min": 80, "temp_min": 15},
            "aflatoxin": {"humidity_min": 85, "temp_min": 28},  # serious — FDA limits
        },
        "moisture_target_pct": 15.5  # grain moisture for safe storage
    },
    "wheat": {
        "ideal_temp_max": 30, "ideal_humidity_max": 60,
        "rain_sensitivity": "VERY_HIGH",  # sprouting risk
        "quality_risks": {
            "sprouting": {"rain_mm_3d": 10, "humidity_min": 80},
            "fusarium": {"temp_range": (15, 30), "humidity_min": 85}
        },
        "moisture_target_pct": 13.5
    },
    "soybeans": {
        "ideal_temp_max": 30, "ideal_humidity_max": 65,
        "rain_sensitivity": "MEDIUM",
        "quality_risks": {
            "mold": {"humidity_min": 85, "temp_min": 20},
            "pod_shatter": {"humidity_fluctuation": 30}  # rapid humidity swings
        },
        "moisture_target_pct": 13.0
    },
    "hay": {
        "ideal_temp_max": 32, "ideal_humidity_max": 55,
        "rain_sensitivity": "VERY_HIGH",
        "quality_risks": {
            "mold": {"rain_mm_any": 2.0},
            "nutrient_loss": {"rain_mm_any": 5.0}
        },
        "moisture_target_pct": 18.0
    }
}
```

**Step 2 — Harvest window scorer**
```python
def compute_harvest_quality(ag_data: dict, crop: str) -> dict:
    daily = ag_data["daily"]
    hourly = ag_data["hourly"]
    rules = HARVEST_QUALITY_RULES.get(crop)
    if not rules:
        return {"error": f"Crop {crop} not supported"}

    windows = []
    cumulative_rain_3d = sum(daily["precipitation_sum"][:3])

    for i in range(7):
        temp_max = daily["temperature_2m_max"][i]
        temp_min = daily["temperature_2m_min"][i]
        rain = daily["precipitation_sum"][i]

        # Hourly humidity for the day
        day_humidity = hourly["relative_humidity_2m"][i*24:(i+1)*24]
        avg_humidity = sum(day_humidity) / len(day_humidity) if day_humidity else 70
        humidity_swing = max(day_humidity) - min(day_humidity) if day_humidity else 0

        # Score: start at 100, deduct for each risk
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

        # Check specific crop quality risks
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

        windows.append({
            "date": daily["time"][i],
            "quality_score": quality_score,
            "grade": grade,
            "rain_mm": round(rain, 1),
            "avg_humidity_pct": round(avg_humidity, 1),
            "risks": risks_flagged,
            "harvest_recommended": quality_score >= 70 and rain < 2.0
        })

    best_window = max(windows, key=lambda x: x["quality_score"])

    return {
        "crop": crop,
        "moisture_target_pct": rules["moisture_target_pct"],
        "windows": windows,
        "best_harvest_day": best_window,
        "rain_sensitivity": rules["rain_sensitivity"]
    }
```

**Step 3 — FastAPI + Streamlit**
```python
# FastAPI
@app.get("/agriculture/harvest-quality")
def harvest_quality(lat: float, lon: float, crop: str = "corn"):
    ag_data = fetch_agriculture_data(lat, lon)
    return compute_harvest_quality(ag_data, crop)

# Streamlit
st.subheader("🌾 Harvest Quality Predictor")
crop = st.selectbox("Crop to Harvest", list(HARVEST_QUALITY_RULES.keys()))

result = requests.get(f"{API}/agriculture/harvest-quality",
    params={"lat": lat, "lon": lon, "crop": crop}).json()

best = result["best_harvest_day"]
st.success(f"🏆 Best harvest window: **{best['date']}** — Score {best['quality_score']}/100 ({best['grade']})")
st.caption(f"Target grain moisture: {result['moisture_target_pct']}% | Rain sensitivity: {result['rain_sensitivity']}")

for w in result["windows"]:
    icon = "✅" if w["harvest_recommended"] else "❌"
    with st.expander(f"{icon} {w['date']} — Score: {w['quality_score']}/100 | {w['grade']}"):
        st.write(f"Rain: {w['rain_mm']}mm | Avg Humidity: {w['avg_humidity_pct']}%")
        for risk in w["risks"]:
            st.warning(risk)
        if not w["risks"]:
            st.success("No quality risks detected")
```

Start by adding `et0_fao_evapotranspiration` and `shortwave_radiation` to your existing fetch call and all 5 features unlock immediately.



