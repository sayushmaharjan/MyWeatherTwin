# 🚗 Travel & Commute — Full Implementation

Same stack as before: Open-Meteo + FastAPI + Streamlit. Zero new API keys needed for Road Conditions and Travel Window. Flight Delay needs one free API.

**Impact order:** Road Condition Predictor → Best Travel Window → Flight Delay Risk

---

## 1. 🧊 Road Condition Predictor

**Why first:** Black ice kills. This is the single highest life-safety feature in the entire app. Universally relevant every winter.

**Core concept:** Black ice forms when surface temp ≤ 0°C + moisture present. It's invisible — raw temperature alone never tells you this.

**Step 1 — Fetch the right variables**

Add to your existing `fetch_openmeteo()` call:

```python
def fetch_road_weather(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m",
            "dewpoint_2m",              # key for frost formation
            "surface_temperature",      # road surface ≠ air temp
            "precipitation",
            "rain",
            "snowfall",
            "snow_depth",
            "visibility",               # fog detection
            "windspeed_10m",
            "freezing_level_height",    # 0 = freezing at surface
            "wet_bulb_temperature_2m",  # most accurate for ice formation
        ],
        "daily": [
            "temperature_2m_min",
            "temperature_2m_max",
            "precipitation_sum",
            "snowfall_sum",
        ],
        "forecast_days": 7,
        "timezone": "auto"
    }
    return requests.get("https://api.open-meteo.com/v1/forecast", params=params).json()
```

**Step 2 — Black ice probability engine**

```python
def compute_black_ice_probability(hourly: dict, hour_index: int) -> dict:
    """
    Black ice forms when:
    1. Surface temp at or below 0°C
    2. Moisture present (recent rain, dew, or snow melt)
    3. Often AFTER a freeze-thaw cycle
    
    Most dangerous: 11pm–7am when roads aren't treated
    """
    temp = hourly["temperature_2m"][hour_index]
    surface_temp = hourly.get("surface_temperature", hourly["temperature_2m"])[hour_index]
    dewpoint = hourly["dewpoint_2m"][hour_index]
    wet_bulb = hourly["wet_bulb_temperature_2m"][hour_index]
    precip = hourly["precipitation"][hour_index]
    rain_prev3 = sum(hourly["rain"][max(0, hour_index-3):hour_index])  # rain in last 3hrs
    snowfall = hourly["snowfall"][hour_index]
    snow_depth = hourly["snow_depth"][hour_index]

    risk_score = 0
    factors = []

    # Factor 1: Surface temperature at or near freezing
    if surface_temp <= 0:
        risk_score += 40
        factors.append(f"Road surface at {surface_temp:.1f}°C (at/below freezing)")
    elif surface_temp <= 2:
        risk_score += 20
        factors.append(f"Road surface near freezing ({surface_temp:.1f}°C)")

    # Factor 2: Wet bulb at/below 0 = freezing of moisture guaranteed
    if wet_bulb <= 0:
        risk_score += 25
        factors.append("Wet bulb temp ≤0°C — any moisture will freeze on contact")

    # Factor 3: Recent rain on cold surface = instant black ice
    if rain_prev3 > 0.5 and surface_temp <= 2:
        risk_score += 30
        factors.append(f"Recent rain ({rain_prev3:.1f}mm) on near-freezing surface")

    # Factor 4: Freeze-thaw cycle (air temp crossing 0 recently)
    temps_past6 = hourly["temperature_2m"][max(0, hour_index-6):hour_index]
    if temps_past6:
        had_thaw = any(t > 2 for t in temps_past6)
        now_freezing = temp <= 0
        if had_thaw and now_freezing:
            risk_score += 20
            factors.append("Freeze-thaw cycle detected — melted moisture refreezing")

    # Factor 5: Dewpoint spread (condensation → frost)
    dew_spread = temp - dewpoint
    if dew_spread <= 1 and temp <= 3:
        risk_score += 15
        factors.append(f"Dewpoint near air temp ({dew_spread:.1f}°C spread) — frost forming")

    # Factor 6: Snow depth (packed snow → ice)
    if snow_depth > 0 and surface_temp <= 0:
        risk_score += 10
        factors.append(f"Snow pack present ({snow_depth}cm) — compaction ice risk")

    risk_score = min(risk_score, 100)

    # Stopping distance multipliers (from UK Highway Code research)
    if risk_score >= 70:
        stopping_multiplier = 10    # 10x normal stopping distance on black ice
        condition = "BLACK ICE LIKELY"
        icon = "🔴"
    elif risk_score >= 40:
        stopping_multiplier = 3     # wet/slushy roads
        condition = "ICY PATCHES POSSIBLE"
        icon = "🟠"
    elif risk_score >= 20:
        stopping_multiplier = 2
        condition = "SLIPPERY CONDITIONS"
        icon = "🟡"
    else:
        stopping_multiplier = 1
        condition = "NORMAL CONDITIONS"
        icon = "🟢"

    return {
        "risk_score": risk_score,
        "condition": condition,
        "icon": icon,
        "stopping_distance_multiplier": stopping_multiplier,
        "risk_factors": factors,
        "surface_temp_c": surface_temp,
        "air_temp_c": temp
    }


def compute_fog_risk(hourly: dict, hour_index: int) -> dict:
    """
    Radiation fog forms on clear nights when humidity is high.
    Advection fog forms when warm moist air moves over cold surface.
    """
    visibility = hourly.get("visibility", [10000] * 24)[hour_index]
    temp = hourly["temperature_2m"][hour_index]
    dewpoint = hourly["dewpoint_2m"][hour_index]
    dew_spread = temp - dewpoint

    # Fog = visibility < 1000m (legal definition in most countries)
    if visibility < 200:
        density, icon = "DENSE FOG", "🔴"
        speed_advice = "Do not drive — or max 20 km/h with hazard lights"
    elif visibility < 500:
        density, icon = "THICK FOG", "🟠"
        speed_advice = "Reduce speed to 40 km/h, use low beam headlights"
    elif visibility < 1000:
        density, icon = "MODERATE FOG", "🟡"
        speed_advice = "Reduce speed, increase following distance to 4 seconds"
    elif dew_spread <= 2 and temp <= 10:
        density, icon = "FOG POSSIBLE", "🟡"
        speed_advice = "Be alert — fog may form, especially in valleys and low areas"
    else:
        density, icon = "CLEAR", "🟢"
        speed_advice = "Normal driving conditions"

    return {
        "visibility_m": visibility,
        "density": density,
        "icon": icon,
        "speed_advice": speed_advice,
        "dew_spread": round(dew_spread, 1)
    }


def compute_road_conditions(road_data: dict) -> dict:
    """Master road condition analyzer — next 24 hours"""
    hourly = road_data["hourly"]
    results = []

    for i in range(24):
        ice = compute_black_ice_probability(hourly, i)
        fog = compute_fog_risk(hourly, i)

        # Combined danger score
        combined_score = max(ice["risk_score"], 
                            100 if fog["visibility_m"] < 200 else
                            60 if fog["visibility_m"] < 500 else
                            30 if fog["visibility_m"] < 1000 else 0)

        results.append({
            "hour": i,
            "time_label": hourly["time"][i][11:16],
            "ice": ice,
            "fog": fog,
            "combined_danger": combined_score,
            "safe_to_drive": combined_score < 30
        })

    # Find worst and best windows
    worst = max(results, key=lambda x: x["combined_danger"])
    safe_windows = [r for r in results if r["safe_to_drive"]]

    return {
        "hourly": results,
        "worst_hour": worst,
        "safe_hours_count": len(safe_windows),
        "current": results[0],
        "peak_danger_time": worst["time_label"],
        "peak_danger_score": worst["combined_danger"]
    }
```

**Step 3 — FastAPI route**

```python
@app.get("/travel/road-conditions")
def road_conditions(lat: float, lon: float):
    data = fetch_road_weather(lat, lon)
    return compute_road_conditions(data)
```

**Step 4 — Streamlit UI**

```python
st.subheader("🧊 Road Condition Predictor")

result = requests.get(f"{API}/travel/road-conditions",
    params={"lat": lat, "lon": lon}).json()

current = result["current"]
worst = result["worst_hour"]

col1, col2, col3 = st.columns(3)
col1.metric(
    f"{current['ice']['icon']} Road Surface",
    current["ice"]["condition"],
    f"{current['ice']['surface_temp_c']}°C surface"
)
col2.metric(
    f"{current['fog']['icon']} Visibility",
    f"{current['fog']['visibility_m']}m",
    current["fog"]["density"]
)
col3.metric(
    "⚠️ Stopping Distance",
    f"{current['ice']['stopping_distance_multiplier']}x normal",
    help="Multiplier vs dry road stopping distance"
)

# Risk factors
if current["ice"]["risk_factors"]:
    st.error("**Active risk factors:**")
    for f in current["ice"]["risk_factors"]:
        st.write(f"  • {f}")

st.caption(current["fog"]["speed_advice"])

# 24hr timeline
st.subheader("24-Hour Road Risk Timeline")
import pandas as pd
df = pd.DataFrame([{
    "Time": r["time_label"],
    "Ice Risk": r["ice"]["risk_score"],
    "Visibility (m)": r["fog"]["visibility_m"],
    "Safe": "✅" if r["safe_to_drive"] else "⚠️"
} for r in result["hourly"]])
st.dataframe(df, use_container_width=True)
```

---

## 2. 🗓️ Best Travel Window (7-Day Road Trip Planner)

**Core concept:** Score each day across an origin→destination corridor. Account for weather at both ends and estimated midpoint.

**Step 1 — Multi-point corridor scorer**

```python
def compute_travel_window(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    trip_hours: float = 4.0         # estimated drive time
) -> dict:
    """
    Fetches weather at origin, destination, and midpoint.
    Scores each day 0–100 for travel safety.
    """
    mid_lat = (origin_lat + dest_lat) / 2
    mid_lon = (origin_lon + dest_lon) / 2

    # Fetch all three points
    origin_data = fetch_road_weather(origin_lat, origin_lon)
    dest_data = fetch_road_weather(dest_lat, dest_lon)
    mid_data = fetch_road_weather(mid_lat, mid_lon)

    daily_scores = []

    for i in range(7):
        day_scores = []

        for point_data, label in [
            (origin_data, "origin"),
            (mid_data, "midpoint"),
            (dest_data, "destination")
        ]:
            d = point_data["daily"]
            temp_min = d["temperature_2m_min"][i]
            temp_max = d["temperature_2m_max"][i]
            precip = d["precipitation_sum"][i]
            snow = d["snowfall_sum"][i]

            # Score this point/day
            score = 100

            # Precipitation penalty
            if precip > 20:
                score -= 40
            elif precip > 10:
                score -= 25
            elif precip > 2:
                score -= 10

            # Snow penalty (heavy)
            if snow > 10:
                score -= 50
            elif snow > 2:
                score -= 30
            elif snow > 0:
                score -= 15

            # Freezing conditions
            if temp_min <= 0 and precip > 0:
                score -= 25     # rain/snow on freezing roads
            if temp_min <= -10:
                score -= 15     # extreme cold = mechanical issues

            day_scores.append({"point": label, "score": max(0, score)})

        # Worst point in the corridor determines the day's score
        corridor_score = min(s["score"] for s in day_scores)
        worst_point = min(day_scores, key=lambda x: x["score"])

        # Get day label
        from datetime import datetime, timedelta
        day_label = (datetime.now() + timedelta(days=i)).strftime("%A, %b %d")
        if i == 0: day_label = "Today"
        if i == 1: day_label = "Tomorrow"

        daily_scores.append({
            "day": day_label,
            "date": origin_data["daily"]["time"][i],
            "corridor_score": corridor_score,
            "point_scores": day_scores,
            "worst_point": worst_point["point"],
            "grade": ("🟢 Excellent" if corridor_score >= 85 else
                      "🟡 Good"      if corridor_score >= 70 else
                      "🟠 Fair"      if corridor_score >= 50 else
                      "🔴 Poor — consider postponing"),
            "origin_precip": origin_data["daily"]["precipitation_sum"][i],
            "dest_precip": dest_data["daily"]["precipitation_sum"][i],
            "origin_snow": origin_data["daily"]["snowfall_sum"][i],
        })

    best_day = max(daily_scores, key=lambda x: x["corridor_score"])

    return {
        "daily_scores": daily_scores,
        "best_travel_day": best_day,
        "trip_hours": trip_hours
    }
```

**Step 2 — FastAPI route**

```python
@app.get("/travel/best-window")
def best_travel_window(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    trip_hours: float = 4.0
):
    return compute_travel_window(origin_lat, origin_lon,
                                  dest_lat, dest_lon, trip_hours)
```

**Step 3 — Streamlit UI with destination input**

```python
st.subheader("🗓️ Best Travel Window")

col1, col2 = st.columns(2)
with col1:
    st.write("**Origin** (auto-detected from your location)")
    origin_lat = st.session_state.lat
    origin_lon = st.session_state.lon
with col2:
    dest_city = st.text_input("Destination city", placeholder="Chicago, IL")
    trip_hrs = st.slider("Estimated drive time (hours)", 1.0, 12.0, 4.0, 0.5)

if dest_city:
    # Geocode destination using Open-Meteo geocoding (free)
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
        params={"name": dest_city, "count": 1}).json()
    
    if geo.get("results"):
        dest = geo["results"][0]
        result = requests.get(f"{API}/travel/best-window", params={
            "origin_lat": origin_lat, "origin_lon": origin_lon,
            "dest_lat": dest["latitude"], "dest_lon": dest["longitude"],
            "trip_hours": trip_hrs
        }).json()

        best = result["best_travel_day"]
        st.success(f"🏆 Best day to travel: **{best['day']}** — Score {best['corridor_score']}/100 ({best['grade']})")

        for day in result["daily_scores"]:
            with st.expander(f"{day['grade']} — {day['day']} (Score: {day['corridor_score']}/100)"):
                col1, col2 = st.columns(2)
                col1.write(f"Origin rain/snow: {day['origin_precip']}mm / {day['origin_snow']}cm")
                col2.write(f"Destination rain/snow: {day['dest_precip']}mm")
                if day["corridor_score"] < 70:
                    st.warning(f"Worst conditions at: **{day['worst_point']}**")
```

---

## 3. ✈️ Flight Delay Risk

**This one needs one free API:** [AviationWeather.gov](https://aviationweather.gov/api) — US government, completely free, no key needed.

**Step 1 — Fetch METARs and TAFs (aviation weather)**

```python
AVIATION_BASE = "https://aviationweather.gov/api/data"

def fetch_airport_weather(icao_code: str) -> dict:
    """
    METAR = current observed conditions at airport
    TAF   = terminal aerodrome forecast (24–30hr)
    ICAO examples: KORD (Chicago O'Hare), KJFK (JFK), KLAX (LAX)
    """
    metar = requests.get(f"{AVIATION_BASE}/metar",
        params={"ids": icao_code, "format": "json"}).json()
    taf = requests.get(f"{AVIATION_BASE}/taf",
        params={"ids": icao_code, "format": "json"}).json()
    return {"metar": metar, "taf": taf, "icao": icao_code}


def parse_delay_risk(airport_data: dict) -> dict:
    """
    Delay causes by probability:
    1. Thunderstorms (most common, unpredictable)
    2. Low visibility / fog (Ground Stop triggers)
    3. Wind shear / crosswinds (runway capacity drops)
    4. Heavy snow/ice (de-icing queues, ramp closures)
    5. Low ceilings (IFR conditions slow arrival rates)
    """
    metar = airport_data["metar"]
    if not metar:
        return {"error": "Airport data unavailable", "icao": airport_data["icao"]}

    m = metar[0] if isinstance(metar, list) else metar

    # Extract key fields from METAR
    visibility_sm = m.get("visib", 10)      # statute miles
    wind_speed_kt = m.get("wspd", 0)        # knots
    wind_gust_kt = m.get("wgst", 0)
    sky_conditions = m.get("skyCondition", [])
    wx_string = m.get("wxString", "")       # weather phenomena (TS, FG, SN etc)
    temp_c = m.get("temp", 10)

    delay_score = 0
    delay_reasons = []

    # Thunderstorm — biggest delay cause
    if "TS" in wx_string:
        delay_score += 50
        delay_reasons.append("⛈️ Active thunderstorms — ground stops likely")

    # Visibility / fog
    if visibility_sm < 0.25:
        delay_score += 45
        delay_reasons.append(f"🌫️ Near-zero visibility ({visibility_sm}sm) — Ground Stop possible")
    elif visibility_sm < 1:
        delay_score += 30
        delay_reasons.append(f"🌫️ Low visibility ({visibility_sm}sm) — IFR conditions")
    elif visibility_sm < 3:
        delay_score += 15
        delay_reasons.append(f"🌫️ Reduced visibility ({visibility_sm}sm) — reduced arrival rate")

    # Ceiling height
    for sky in sky_conditions:
        coverage = sky.get("skyCover", "")
        height_ft = sky.get("cloudBase", 9999)
        if coverage in ["BKN", "OVC"]:
            if height_ft < 500:
                delay_score += 35
                delay_reasons.append(f"☁️ Very low ceiling ({height_ft}ft) — ILS approaches only")
            elif height_ft < 1000:
                delay_score += 20
                delay_reasons.append(f"☁️ Low ceiling ({height_ft}ft) — reduced capacity")
            break

    # Wind / crosswind
    effective_wind = max(wind_speed_kt, wind_gust_kt * 0.8 if wind_gust_kt else 0)
    if effective_wind > 35:
        delay_score += 30
        delay_reasons.append(f"💨 Strong winds ({effective_wind:.0f}kt) — crosswind limits possible")
    elif effective_wind > 25:
        delay_score += 15
        delay_reasons.append(f"💨 Gusty winds ({effective_wind:.0f}kt) — reduced runway throughput")

    # Snow / ice
    if "SN" in wx_string or "FZRA" in wx_string:
        delay_score += 35
        delay_reasons.append("❄️ Snow/freezing rain — de-icing queues, ramp slowdowns")
    elif "RA" in wx_string and temp_c <= 2:
        delay_score += 20
        delay_reasons.append("🌧️ Rain near freezing — icing risk on aircraft surfaces")

    delay_score = min(delay_score, 100)

    return {
        "icao": airport_data["icao"],
        "delay_risk_score": delay_score,
        "risk_level": ("🔴 High" if delay_score >= 60 else
                       "🟠 Moderate" if delay_score >= 30 else
                       "🟢 Low"),
        "delay_reasons": delay_reasons,
        "visibility_sm": visibility_sm,
        "wind_kt": wind_speed_kt,
        "conditions_summary": wx_string or "No significant weather",
        "raw_temp_c": temp_c
    }
```

**Step 2 — FastAPI route**

```python
@app.get("/travel/flight-delay")
def flight_delay_risk(origin_icao: str, dest_icao: str):
    origin_wx = fetch_airport_weather(origin_icao.upper())
    dest_wx = fetch_airport_weather(dest_icao.upper())
    return {
        "origin": parse_delay_risk(origin_wx),
        "destination": parse_delay_risk(dest_wx),
        "overall_risk": max(
            parse_delay_risk(origin_wx)["delay_risk_score"],
            parse_delay_risk(dest_wx)["delay_risk_score"]
        )
    }
```

**Step 3 — Streamlit UI with ICAO lookup helper**

```python
st.subheader("✈️ Flight Delay Risk")

# Common airport lookup so users don't need to know ICAO codes
AIRPORT_LOOKUP = {
    "Chicago O'Hare": "KORD", "JFK New York": "KJFK",
    "LAX Los Angeles": "KLAX", "Dallas/Fort Worth": "KDFW",
    "Atlanta Hartsfield": "KATL", "Denver": "KDEN",
    "San Francisco": "KSFO", "Miami": "KMIA",
    "Seattle": "KSEA", "Boston Logan": "KBOS",
    "Las Vegas": "KLAS", "Phoenix": "KPHX",
    "Minneapolis": "KMSP", "Detroit": "KDTW",
    "Other (enter ICAO code)": "custom"
}

col1, col2 = st.columns(2)
with col1:
    origin_select = st.selectbox("Departure Airport", list(AIRPORT_LOOKUP.keys()))
    if origin_select == "Other (enter ICAO code)":
        origin_icao = st.text_input("Origin ICAO code (e.g. KORD)")
    else:
        origin_icao = AIRPORT_LOOKUP[origin_select]

with col2:
    dest_select = st.selectbox("Arrival Airport", list(AIRPORT_LOOKUP.keys()))
    if dest_select == "Other (enter ICAO code)":
        dest_icao = st.text_input("Destination ICAO code")
    else:
        dest_icao = AIRPORT_LOOKUP[dest_select]

if origin_icao and dest_icao and origin_icao != dest_icao:
    result = requests.get(f"{API}/travel/flight-delay",
        params={"origin_icao": origin_icao, "dest_icao": dest_icao}).json()

    col1, col2 = st.columns(2)
    for col, airport_key, label in [
        (col1, "origin", f"🛫 {origin_select}"),
        (col2, "destination", f"🛬 {dest_select}")
    ]:
        data = result[airport_key]
        with col:
            st.metric(label, data["risk_level"],
                      f"Score: {data['delay_risk_score']}/100")
            st.caption(f"Visibility: {data['visibility_sm']}sm | "
                      f"Wind: {data['wind_kt']}kt")
            for reason in data["delay_reasons"]:
                st.warning(reason)
            if not data["delay_reasons"]:
                st.success("✅ No significant weather delays expected")
```

---

# 🏥 Substance Use Public Health Dashboard
Create a new tab for this feature.

**The reframe:** Instead of scanning individuals, this aggregates **already-published** public health data from CDC and NIDA into a local-area awareness and resource tool. Think of it as a "weather map for public health risk" — the same way WeatherTwin shows climate risk, this shows community-level substance use risk signals.

**Architecture:**

```
CDC/NIDA Data (batch ingested) → PostgreSQL/SQLite
        ↓
FastAPI analytics layer
        ↓
LLM summarization (Groq) → narrative insights
        ↓
Streamlit dashboard → maps, trends, resource locator
```

---

## Part 1 — Data Ingestion Pipeline

Create `backend/public_health/ingestion.py`:

```python
import requests
import pandas as pd
import sqlite3
from datetime import datetime

DB_PATH = "data/public_health.db"

# ── CDC Overdose Data (Socrata API — no key needed for basic use) ──
def ingest_cdc_overdose_data():
    """
    CDC Drug Overdose Deaths — state/county level, monthly
    Dataset: https://data.cdc.gov/resource/xkb8-kh2a.json
    """
    url = "https://data.cdc.gov/resource/xkb8-kh2a.json"
    params = {
        "$limit": 50000,
        "$order": "year DESC",
        # Filter to most recent 5 years
        "$where": f"year >= {datetime.now().year - 5}"
    }
    response = requests.get(url, params=params)
    data = response.json()
    df = pd.DataFrame(data)

    # Normalize columns
    df = df.rename(columns={
        "state": "state",
        "year": "year",
        "month": "month",
        "indicator": "substance_type",
        "data_value": "death_count",
        "footnote": "notes"
    })
    df["death_count"] = pd.to_numeric(df["death_count"], errors="coerce")
    df["ingested_at"] = datetime.now().isoformat()

    _save_to_db(df, "cdc_overdose")
    print(f"✅ Ingested {len(df)} CDC overdose records")
    return df


def ingest_treatment_locator():
    """
    SAMHSA Treatment Facility Locator API (free, no key)
    Provides facility locations, services, accepting status
    """
    url = "https://findtreatment.samhsa.gov/locator/listing"
    # Returns facilities with lat/lon, services, insurance accepted
    params = {"pageSize": 200, "page": 1}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data.get("rows", []))
        df["ingested_at"] = datetime.now().isoformat()
        _save_to_db(df, "treatment_facilities")
        print(f"✅ Ingested {len(df)} treatment facility records")
    return df


def ingest_nida_stats():
    """
    NIDA publishes annual survey stats (NSDUH).
    These are static tables — we load from curated CSVs.
    Source: https://nida.nih.gov/research-topics/trends-statistics
    
    Data points: past-year use rates by substance, age group, state
    """
    # NSDUH state-level estimates (pre-downloaded from NIDA)
    # Download from: https://www.samhsa.gov/data/nsduh/state-reports
    nsduh_url = ("https://www.samhsa.gov/data/sites/default/files/"
                 "reports/rpt39441/NSDUHsaePercentsExcelCSVs2021/"
                 "NSDUHsaePercents2021.csv")
    
    try:
        df = pd.read_csv(nsduh_url)
        df["source"] = "NSDUH_2021"
        df["ingested_at"] = datetime.now().isoformat()
        _save_to_db(df, "nsduh_state_estimates")
        print(f"✅ Ingested {len(df)} NSDUH records")
    except Exception as e:
        print(f"⚠️ NSDUH ingestion failed: {e} — use manual CSV download")
    return None


def _save_to_db(df: pd.DataFrame, table_name: str):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()


def run_full_ingestion():
    """Run all ingestion jobs — schedule this daily with cron or APScheduler"""
    import os
    os.makedirs("data", exist_ok=True)
    ingest_cdc_overdose_data()
    ingest_treatment_locator()
    ingest_nida_stats()
    print("✅ Full ingestion complete")


if __name__ == "__main__":
    run_full_ingestion()
```

---

## Part 2 — Analytics Layer

Create `backend/public_health/analytics.py`:

```python
import sqlite3
import pandas as pd
from typing import Optional

DB_PATH = "data/public_health.db"

def get_db():
    return sqlite3.connect(DB_PATH)


def get_state_overdose_trend(state: str, substance: Optional[str] = None) -> dict:
    """
    Returns monthly overdose death counts for a state.
    Detects spikes using rolling average comparison.
    """
    conn = get_db()
    query = """
        SELECT year, month, substance_type, 
               AVG(death_count) as deaths
        FROM cdc_overdose
        WHERE state = ?
    """
    params = [state]
    if substance:
        query += " AND substance_type LIKE ?"
        params.append(f"%{substance}%")

    query += " GROUP BY year, month, substance_type ORDER BY year, month"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return {"error": f"No data found for {state}"}

    # Rolling 3-month average for spike detection
    df["rolling_avg"] = df["deaths"].rolling(3, min_periods=1).mean()
    df["spike"] = df["deaths"] > (df["rolling_avg"] * 1.3)   # 30% above average = spike

    # YoY change
    latest_year = df["year"].max()
    prev_year = str(int(latest_year) - 1)
    current_avg = df[df["year"] == latest_year]["deaths"].mean()
    prev_avg = df[df["year"] == prev_year]["deaths"].mean() if prev_year in df["year"].values else None
    yoy_change_pct = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg else None

    return {
        "state": state,
        "substance_filter": substance,
        "total_records": len(df),
        "latest_year": latest_year,
        "current_year_avg_monthly": round(current_avg, 1),
        "yoy_change_pct": round(yoy_change_pct, 1) if yoy_change_pct else None,
        "spike_months": df[df["spike"]]["month"].tolist(),
        "trend_data": df[["year","month","deaths","rolling_avg","spike"]].to_dict("records"),
        "substances_tracked": df["substance_type"].unique().tolist()
    }


def get_national_heatmap_data() -> list[dict]:
    """
    Aggregate overdose deaths by state for choropleth map.
    Returns most recent year data.
    """
    conn = get_db()
    query = """
        SELECT state, 
               SUM(death_count) as total_deaths,
               year
        FROM cdc_overdose
        WHERE year = (SELECT MAX(year) FROM cdc_overdose)
        GROUP BY state, year
        ORDER BY total_deaths DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df.to_dict("records")


def get_substance_breakdown(state: str) -> list[dict]:
    """What substances are driving overdoses in a given state?"""
    conn = get_db()
    query = """
        SELECT substance_type,
               SUM(death_count) as total_deaths,
               COUNT(*) as months_reported
        FROM cdc_overdose
        WHERE state = ?
          AND year = (SELECT MAX(year) FROM cdc_overdose)
        GROUP BY substance_type
        ORDER BY total_deaths DESC
        LIMIT 10
    """
    df = pd.read_sql_query(query, conn, params=[state])
    conn.close()
    return df.to_dict("records")


def get_nearby_treatment_facilities(
    lat: float, lon: float, radius_miles: float = 25
) -> list[dict]:
    """
    Return treatment facilities within radius using Haversine distance.
    """
    conn = get_db()
    query = "SELECT * FROM treatment_facilities"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty or "latitude" not in df.columns:
        return []

    import math
    def haversine(lat1, lon1, lat2, lon2):
        R = 3958.8  # Earth radius in miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) *
             math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    df["distance_miles"] = df.apply(
        lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1)
    
    nearby = df[df["distance_miles"] <= radius_miles].sort_values("distance_miles")
    return nearby.head(10).to_dict("records")
```

---

## Part 3 — LLM Narrative Summarization

This is where Groq turns raw numbers into actionable public health insights.

Create `backend/public_health/summarizer.py`:

```python
from groq import Groq
from .analytics import (get_state_overdose_trend, get_substance_breakdown,
                         get_national_heatmap_data)

client = Groq()

PUBLIC_HEALTH_SYSTEM_PROMPT = """
You are a public health data analyst assistant embedded in a community 
awareness dashboard. You summarize aggregated, anonymized public health 
statistics to help community members, social workers, and local officials 
understand substance use trends in their area.

## Your role
- Translate statistical data into clear, empathetic plain-language summaries
- Always frame findings in terms of community impact, not individual blame
- Highlight actionable resources (treatment, hotlines, prevention programs)
- Never speculate about causes beyond what the data shows
- Use person-first language (e.g., "people experiencing addiction" not "addicts")

## Hard rules
- You are summarizing AGGREGATE population statistics only
- Never make inferences about any individual person
- Always note that these are official CDC/NIDA reported figures
- End every summary with relevant support resources
- If asked about specific individuals, decline and redirect to aggregate data
"""

def generate_state_summary(state: str, substance: str = None) -> str:
    """Generate an LLM narrative summary of state overdose trends"""

    trend = get_state_overdose_trend(state, substance)
    breakdown = get_substance_breakdown(state)

    if "error" in trend:
        return f"Insufficient data available for {state}."

    # Build data context for LLM
    context = f"""
## Overdose Trend Data — {state}
- Most recent year: {trend['latest_year']}
- Average monthly overdose deaths: {trend['current_year_avg_monthly']}
- Year-over-year change: {trend['yoy_change_pct']}% vs previous year
- Spike months detected: {trend['spike_months'] or 'None identified'}
- Substances tracked: {', '.join(trend['substances_tracked'][:5])}

## Substance Breakdown (Top causes)
{chr(10).join([f"- {s['substance_type']}: {s['total_deaths']} deaths ({s['months_reported']} months reported)" 
               for s in breakdown[:5]])}

Data source: CDC Drug Overdose Surveillance System (official reported figures)
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": PUBLIC_HEALTH_SYSTEM_PROMPT},
            {"role": "user", "content": f"""
Write a 3-paragraph public health summary for {state} based on this data.

{context}

Structure:
1. Current situation — what the numbers show
2. Trend analysis — improving, worsening, or stable, and which substances
3. Community resources and what people can do

Keep it under 250 words. Plain language. Empathetic tone.
"""}
        ],
        max_tokens=400,
        temperature=0.3,
        stream=False
    )

    return response.choices[0].message.content


def generate_trend_alert(state: str) -> dict:
    """
    Detects if a state has an emerging spike and generates an alert summary.
    Used for the dashboard's proactive alert system.
    """
    trend = get_state_overdose_trend(state)

    if "error" in trend:
        return {"has_alert": False}

    spike_detected = len(trend["spike_months"]) > 0
    yoy_worsening = (trend["yoy_change_pct"] or 0) > 10  # 10%+ YoY increase

    if not spike_detected and not yoy_worsening:
        return {"has_alert": False, "state": state}

    # Generate alert narrative
    alert_context = f"""
State: {state}
Spike months: {trend['spike_months']}
YoY change: {trend['yoy_change_pct']}%
Monthly average: {trend['current_year_avg_monthly']} deaths
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": PUBLIC_HEALTH_SYSTEM_PROMPT},
            {"role": "user", "content": f"""
Write a 2-sentence public health alert (NOT alarmist, factual and constructive) 
for this emerging trend. Include one specific action community members can take.

{alert_context}
"""}
        ],
        max_tokens=100,
        temperature=0.2
    )

    return {
        "has_alert": True,
        "state": state,
        "spike_detected": spike_detected,
        "yoy_worsening": yoy_worsening,
        "alert_text": response.choices[0].message.content,
        "yoy_change_pct": trend["yoy_change_pct"]
    }
```

---

## Part 4 — Full Streamlit Dashboard

Create `pages/public_health.py`:

```python
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from backend.public_health.analytics import (
    get_state_overdose_trend, get_national_heatmap_data,
    get_substance_breakdown, get_nearby_treatment_facilities
)
from backend.public_health.summarizer import (
    generate_state_summary, generate_trend_alert
)

st.title("🏥 Community Public Health Dashboard")
st.caption("Data source: CDC Drug Overdose Surveillance · SAMHSA · NIDA · All data is aggregated and anonymized")

# ── Disclaimer ────────────────────────────────────────────────────
with st.expander("ℹ️ About this dashboard"):
    st.write("""
    This dashboard displays **aggregated, anonymized public health statistics** 
    from official CDC and NIDA sources. No individual-level data is collected 
    or displayed. The goal is community awareness and resource connection — 
    not surveillance.
    
    If you or someone you know needs help:
    **SAMHSA Helpline: 1-800-662-4357** (free, confidential, 24/7)
    """)

# ── National Heatmap ──────────────────────────────────────────────
st.subheader("📍 National Overdose Overview")

heatmap_data = get_national_heatmap_data()
if heatmap_data:
    df_map = pd.DataFrame(heatmap_data)
    fig = px.choropleth(
        df_map,
        locations="state",
        locationmode="USA-states",
        color="total_deaths",
        scope="usa",
        color_continuous_scale="Reds",
        title=f"Overdose Deaths by State — {df_map['year'].iloc[0] if 'year' in df_map else 'Latest'}",
        labels={"total_deaths": "Deaths"}
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white"
    )
    st.plotly_chart(fig, use_container_width=True)

# ── State Deep Dive ───────────────────────────────────────────────
st.subheader("🔍 State-Level Analysis")

US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID",
             "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS",
             "MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
             "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

col1, col2 = st.columns(2)
with col1:
    selected_state = st.selectbox("Select State", US_STATES,
        index=US_STATES.index("MO") if "MO" in US_STATES else 0)
with col2:
    substance_filter = st.selectbox("Substance Filter",
        ["All substances", "Opioids", "Heroin", "Fentanyl",
         "Cocaine", "Methamphetamine", "Benzodiazepines"])
    substance_param = None if substance_filter == "All substances" else substance_filter

# Trend chart
trend = get_state_overdose_trend(selected_state, substance_param)

if "error" not in trend and trend["trend_data"]:
    df_trend = pd.DataFrame(trend["trend_data"])
    df_trend["period"] = df_trend["year"].astype(str) + "-" + df_trend["month"].astype(str).str.zfill(2)

    fig2 = px.line(df_trend, x="period", y=["deaths", "rolling_avg"],
        title=f"Monthly Overdose Deaths — {selected_state}",
        labels={"value": "Deaths", "period": "Month", "variable": "Series"},
        color_discrete_map={"deaths": "#ef4444", "rolling_avg": "#f97316"})

    # Mark spike months
    spikes = df_trend[df_trend["spike"] == True]
    if not spikes.empty:
        fig2.add_scatter(x=spikes["period"], y=spikes["deaths"],
            mode="markers", marker=dict(size=10, color="red", symbol="star"),
            name="⚠️ Spike detected")

    fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                       plot_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig2, use_container_width=True)

    # Key metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Monthly Deaths", trend["current_year_avg_monthly"])
    col2.metric("Year-over-Year Change",
        f"{trend['yoy_change_pct']}%" if trend["yoy_change_pct"] else "N/A",
        delta=str(trend["yoy_change_pct"]) if trend["yoy_change_pct"] else None)
    col3.metric("Spike Months Detected", len(trend["spike_months"]))

# Substance breakdown
breakdown = get_substance_breakdown(selected_state)
if breakdown:
    df_breakdown = pd.DataFrame(breakdown)
    fig3 = px.bar(df_breakdown, x="substance_type", y="total_deaths",
        title=f"Deaths by Substance — {selected_state}",
        color="total_deaths", color_continuous_scale="Reds")
    fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                       plot_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig3, use_container_width=True)

# ── AI Narrative Summary ──────────────────────────────────────────
st.subheader("🧠 AI Public Health Summary")
if st.button("Generate Summary for " + selected_state):
    with st.spinner("Analyzing data and generating summary..."):
        summary = generate_state_summary(selected_state, substance_param)
    st.info(summary)
    st.caption("Generated from CDC official aggregate statistics · Not individual-level data")

# ── Trend Alert ───────────────────────────────────────────────────
alert = generate_trend_alert(selected_state)
if alert.get("has_alert"):
    st.warning(f"⚠️ **Emerging Trend Alert — {selected_state}**\n\n{alert['alert_text']}")

# ── Treatment Resource Locator ────────────────────────────────────
st.subheader("🏥 Find Treatment Resources Near You")
st.caption("Data from SAMHSA Treatment Facility Locator — updated regularly")

radius = st.slider("Search radius (miles)", 5, 100, 25)
facilities = get_nearby_treatment_facilities(
    lat=st.session_state.lat,
    lon=st.session_state.lon,
    radius_miles=radius
)

if facilities:
    st.write(f"Found **{len(facilities)}** facilities within {radius} miles")
    for f in facilities:
        with st.expander(f"🏥 {f.get('name', 'Treatment Facility')} — {f.get('distance_miles', 0):.1f} miles"):
            st.write(f"**Address:** {f.get('street1','')}, {f.get('city','')}, {f.get('state','')}")
            st.write(f"**Phone:** {f.get('phone','Not listed')}")
            st.write(f"**Services:** {f.get('typeFacility','Not specified')}")
            if f.get("website"):
                st.write(f"**Website:** {f['website']}")
else:
    st.info("No facilities found in range, or facility data not yet loaded.")

st.divider()
st.markdown("""
**Crisis Resources**
- 🆘 **SAMHSA National Helpline:** 1-800-662-4357 (free, confidential, 24/7)
- 🆘 **Crisis Text Line:** Text HOME to 741741
- 🆘 **988 Suicide & Crisis Lifeline:** Call or text 988
""")
```

---

## Final Folder Structure — Complete WeatherTwin

```
weathertwin/
├── backend/
│   ├── main.py
│   ├── context_builder.py
│   ├── prompts.py
│   ├── intent_router.py
│   ├── llm_client.py
│   ├── features/
│   │   ├── health.py
│   │   ├── agriculture.py
│   │   └── travel.py           # ← new
│   └── public_health/          # ← new section
│       ├── ingestion.py
│       ├── analytics.py
│       └── summarizer.py
├── data/
│   └── public_health.db        # SQLite — auto-created on ingestion
├── app.py
└── pages/
    ├── dashboard.py
    ├── health.py
    ├── agriculture.py
    ├── travel.py               # ← new
    ├── chat.py
    └── public_health.py        # ← new
```

---

## Build Order Summary

| Step | Task | Time |
|---|---|---|
| 1 | Add road weather variables to existing fetch call | 30 min |
| 2 | Build `travel.py` backend with all 3 features | 3–4 hrs |
| 3 | Build travel Streamlit page | 2 hrs |
| 4 | Run `ingestion.py` to populate SQLite DB | 1 hr |
| 5 | Build analytics + summarizer modules | 3–4 hrs |
| 6 | Build public health Streamlit page | 2–3 hrs |

The public health dashboard needs **no new LLM infrastructure** — it plugs directly into the Groq client you already have. The only genuinely new dependency is `plotly` for the choropleth map (`pip install plotly`).

Want me to help wire the public health data into the RAG chatbot as well, so users can ask questions like "what's the opioid situation in Missouri?" and get answers backed by real CDC data?