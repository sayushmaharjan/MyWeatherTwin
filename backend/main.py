"""
WeatherTwin — FastAPI Backend
Serves weather intelligence API + static frontend.
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import weather_service as ws
import llm_service as llm

# ─── App Setup ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🌤️  WeatherTwin backend starting...")
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key or groq_key == "your_groq_api_key_here":
        print("⚠️  WARNING: GROQ_API_KEY not set. Chat/AI features will not work.")
        print("   Get a free key at https://console.groq.com")
    else:
        print("✅ Groq API key loaded")
    yield
    print("WeatherTwin shutting down.")


app = FastAPI(
    title="WeatherTwin",
    description="GenAI-powered climate intelligence assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ───────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    city: str
    history: Optional[list] = []


class CompareRequest(BaseModel):
    city1: str
    city2: str


# ─── API Endpoints ────────────────────────────────────────

@app.get("/api/geocode")
async def geocode(city: str = Query(..., min_length=1)):
    """Resolve city name to coordinates."""
    result = await ws.geocode_city(city)
    if not result:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")
    return result


@app.get("/api/weather/current")
async def current_weather(city: str = Query(..., min_length=1)):
    """Get current weather for a city."""
    geo = await ws.geocode_city(city)
    if not geo:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    current = await ws.get_current_weather(geo["latitude"], geo["longitude"])
    return {"city": geo, "current": current}


@app.get("/api/weather/forecast")
async def forecast(city: str = Query(..., min_length=1), days: int = Query(7, ge=1, le=16)):
    """Get weather forecast for a city."""
    geo = await ws.geocode_city(city)
    if not geo:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    fc = await ws.get_forecast(geo["latitude"], geo["longitude"], days)
    return {"city": geo, "forecast": fc}


@app.get("/api/weather/historical")
async def historical(city: str = Query(..., min_length=1), years: int = Query(5, ge=1, le=30)):
    """Get historical climate summary for a city."""
    geo = await ws.geocode_city(city)
    if not geo:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    hist = await ws.get_historical_summary(geo["latitude"], geo["longitude"], years)
    return {"city": geo, "historical": hist}


@app.get("/api/weather/full")
async def full_weather(city: str = Query(..., min_length=1)):
    """Get the complete weather picture: current + forecast + historical + AI insight."""
    geo = await ws.geocode_city(city)
    if not geo:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    lat, lon = geo["latitude"], geo["longitude"]

    # Fetch all data in parallel-ish fashion
    current = await ws.get_current_weather(lat, lon)
    forecast_data = await ws.get_forecast(lat, lon, 7)
    historical_data = await ws.get_historical_summary(lat, lon, 5)

    # Compare current to historical
    comparison = ws.compare_to_historical(current["temperature"], historical_data)

    # Generate AI insight
    insight = ""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and groq_key != "your_groq_api_key_here":
        try:
            insight = await llm.generate_proactive_insight(geo, current, historical_data, comparison)
        except Exception:
            insight = ""

    return {
        "city": geo,
        "current": current,
        "forecast": forecast_data,
        "historical": historical_data,
        "comparison": comparison,
        "insight": insight,
    }

@app.get("/api/weather/full-by-coords")
async def full_weather_by_coords(lat: float = Query(...), lon: float = Query(...)):
    """Get the complete weather picture by coordinates (for map clicks / geolocation)."""
    geo = await ws.reverse_geocode(lat, lon)

    # Fetch all data
    current = await ws.get_current_weather(lat, lon)
    forecast_data = await ws.get_forecast(lat, lon, 7)
    historical_data = await ws.get_historical_summary(lat, lon, 5)

    # Compare current to historical
    comparison = ws.compare_to_historical(current["temperature"], historical_data)

    # Generate AI insight
    insight = ""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and groq_key != "your_groq_api_key_here":
        try:
            insight = await llm.generate_proactive_insight(geo, current, historical_data, comparison)
        except Exception:
            insight = ""

    return {
        "city": geo,
        "current": current,
        "forecast": forecast_data,
        "historical": historical_data,
        "comparison": comparison,
        "insight": insight,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """AI-powered chat with weather context (RAG)."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key or groq_key == "your_groq_api_key_here":
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured. Get a free key at https://console.groq.com")

    # Get city data for RAG context
    geo = await ws.geocode_city(req.city)
    if not geo:
        raise HTTPException(status_code=404, detail=f"City '{req.city}' not found")

    lat, lon = geo["latitude"], geo["longitude"]

    # Build RAG context from real data
    current = await ws.get_current_weather(lat, lon)
    forecast_data = await ws.get_forecast(lat, lon, 7)
    historical_data = await ws.get_historical_summary(lat, lon, 5)
    comparison = ws.compare_to_historical(current["temperature"], historical_data)

    rag_context = llm.build_rag_context(
        geo, current=current, forecast=forecast_data,
        historical=historical_data, comparison=comparison
    )

    # Chat with LLM
    result = await llm.chat_with_context(req.message, rag_context, req.history)
    return result


@app.post("/api/compare")
async def compare_cities(req: CompareRequest):
    """Compare weather between two cities."""
    geo1 = await ws.geocode_city(req.city1)
    geo2 = await ws.geocode_city(req.city2)
    if not geo1:
        raise HTTPException(status_code=404, detail=f"City '{req.city1}' not found")
    if not geo2:
        raise HTTPException(status_code=404, detail=f"City '{req.city2}' not found")

    c1 = await ws.get_current_weather(geo1["latitude"], geo1["longitude"])
    c2 = await ws.get_current_weather(geo2["latitude"], geo2["longitude"])

    h1 = await ws.get_historical_summary(geo1["latitude"], geo1["longitude"], 5)
    h2 = await ws.get_historical_summary(geo2["latitude"], geo2["longitude"], 5)

    comp1 = ws.compare_to_historical(c1["temperature"], h1)
    comp2 = ws.compare_to_historical(c2["temperature"], h2)

    return {
        "city1": {"info": geo1, "current": c1, "historical": h1, "comparison": comp1},
        "city2": {"info": geo2, "current": c2, "historical": h2, "comparison": comp2},
    }


# ─── Health & Wellness API Endpoints ─────────────────────

# Import feature services (path relative to backend/)
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from features.health_weather.service import (
    fetch_openmeteo_health_data, fetch_air_quality,
    compute_sad_index, check_medication_alerts, compute_aq_composite,
    score_exercise_windows, compute_hydration,
)
from features.agriculture.service import (
    fetch_agriculture_data, compute_irrigation_schedule,
    compute_livestock_heat_stress, compute_disease_risk,
    compute_field_work_windows, compute_harvest_quality,
)


@app.get("/api/health/sad-index")
async def sad_index(lat: float = Query(...), lon: float = Query(...)):
    """Get SAD (Seasonal Affective Disorder) risk index."""
    raw = fetch_openmeteo_health_data(lat, lon)
    if "error" in raw:
        raise HTTPException(status_code=502, detail=raw["error"])
    return compute_sad_index(raw.get("daily", {})).model_dump()


@app.get("/api/health/medication-alerts")
async def medication_alerts(lat: float = Query(...), lon: float = Query(...),
                            medications: str = Query(...)):
    """Check medication storage safety. Medications as comma-separated list."""
    med_list = [m.strip() for m in medications.split(",")]
    raw = fetch_openmeteo_health_data(lat, lon)
    if "error" in raw:
        raise HTTPException(status_code=502, detail=raw["error"])
    alerts = check_medication_alerts(raw, med_list)
    return {"alerts": [a.model_dump() for a in alerts]}


@app.get("/api/health/air-quality")
async def air_quality(lat: float = Query(...), lon: float = Query(...)):
    """Get air quality composite score with activity guidance."""
    raw = fetch_air_quality(lat, lon)
    return compute_aq_composite(raw).model_dump()


@app.get("/api/health/exercise-windows")
async def exercise_windows(lat: float = Query(...), lon: float = Query(...)):
    """Get best outdoor exercise time windows for today."""
    raw = fetch_openmeteo_health_data(lat, lon)
    if "error" in raw:
        raise HTTPException(status_code=502, detail=raw["error"])
    windows = score_exercise_windows(raw.get("hourly", {}))
    return {"windows": [w.model_dump() for w in windows]}


@app.get("/api/health/hydration")
async def hydration(lat: float = Query(...), lon: float = Query(...),
                    weight_kg: float = Query(70), activity: str = Query("sedentary")):
    """Estimate daily hydration needs based on weather + activity."""
    raw = fetch_openmeteo_health_data(lat, lon)
    hourly = raw.get("hourly", {})
    temps = hourly.get("temperature_2m", [20])
    hums = hourly.get("relative_humidity_2m", [50])
    # Use current-hour values
    from datetime import datetime
    idx = min(datetime.now().hour, len(temps) - 1) if temps else 0
    temp = temps[idx] if temps[idx] is not None else 20
    hum = hums[idx] if idx < len(hums) and hums[idx] is not None else 50
    return compute_hydration(temp, hum, activity, weight_kg).model_dump()


# ─── Agriculture API Endpoints ───────────────────────────

@app.get("/api/agriculture/irrigation")
async def irrigation_schedule(
    lat: float = Query(...), lon: float = Query(...),
    crop: str = Query("corn"), growth_stage: str = Query("mid"),
    soil_type: str = Query("loam"), area_hectares: float = Query(1.0),
):
    """Get 7-day irrigation schedule."""
    ag_data = fetch_agriculture_data(lat, lon)
    if "error" in ag_data:
        raise HTTPException(status_code=502, detail=ag_data["error"])
    return compute_irrigation_schedule(ag_data, crop, growth_stage, soil_type, area_hectares).model_dump()


@app.get("/api/agriculture/livestock-heat-stress")
async def livestock_heat_stress(lat: float = Query(...), lon: float = Query(...),
                                species: str = Query("dairy_cattle")):
    """Get livestock heat stress (THI) analysis."""
    ag_data = fetch_agriculture_data(lat, lon)
    if "error" in ag_data:
        raise HTTPException(status_code=502, detail=ag_data["error"])
    return compute_livestock_heat_stress(ag_data, species).model_dump()


@app.get("/api/agriculture/disease-risk")
async def disease_risk(lat: float = Query(...), lon: float = Query(...),
                       crops: str = Query(...)):
    """Get crop disease risk alerts. Crops as comma-separated list."""
    crop_list = [c.strip() for c in crops.split(",")]
    ag_data = fetch_agriculture_data(lat, lon)
    if "error" in ag_data:
        raise HTTPException(status_code=502, detail=ag_data["error"])
    alerts = compute_disease_risk(ag_data, crop_list)
    return {"alerts": [a.model_dump() for a in alerts]}


@app.get("/api/agriculture/field-windows")
async def field_windows(lat: float = Query(...), lon: float = Query(...),
                        soil_type: str = Query("loam"), operation: str = Query("harvesting")):
    """Get 7-day field work trafficability windows."""
    ag_data = fetch_agriculture_data(lat, lon)
    if "error" in ag_data:
        raise HTTPException(status_code=502, detail=ag_data["error"])
    windows = compute_field_work_windows(ag_data, soil_type, operation)
    best_day = next((w for w in windows if w.trafficable), None)
    return {
        "windows": [w.model_dump() for w in windows],
        "next_workable_day": best_day.model_dump() if best_day else None,
    }


@app.get("/api/agriculture/harvest-quality")
async def harvest_quality(lat: float = Query(...), lon: float = Query(...),
                          crop: str = Query("corn")):
    """Get harvest quality prediction for a crop."""
    ag_data = fetch_agriculture_data(lat, lon)
    if "error" in ag_data:
        raise HTTPException(status_code=502, detail=ag_data["error"])
    return compute_harvest_quality(ag_data, crop).model_dump()


# ─── Travel & Commute API Endpoints ──────────────────────

from features.travel_planner.service import (
    fetch_road_weather, compute_road_conditions,
    compute_travel_window, compute_flight_delay,
)


@app.get("/api/travel/road-conditions")
async def road_conditions(lat: float = Query(...), lon: float = Query(...)):
    """Get 24-hour road condition prediction (black ice + fog)."""
    data = fetch_road_weather(lat, lon)
    if "error" in data:
        raise HTTPException(status_code=502, detail=data["error"])
    result = compute_road_conditions(data)
    return result.model_dump()


@app.get("/api/travel/best-window")
async def best_travel_window(
    origin_lat: float = Query(...), origin_lon: float = Query(...),
    dest_lat: float = Query(...), dest_lon: float = Query(...),
    trip_hours: float = Query(4.0),
):
    """Get 7-day travel corridor scoring between origin and destination."""
    result = compute_travel_window(origin_lat, origin_lon, dest_lat, dest_lon, trip_hours)
    return result.model_dump()


@app.get("/api/travel/flight-delay")
async def flight_delay_risk(
    origin_icao: str = Query(...), dest_icao: str = Query(...),
):
    """Get flight delay risk for origin + destination airports."""
    result = compute_flight_delay(origin_icao, dest_icao)
    return result.model_dump()


# ─── Public Health API Endpoints ─────────────────────────

from features.public_health.service import (
    get_state_overdose_trend, get_national_heatmap_data,
    get_substance_breakdown,
)


@app.get("/api/public-health/state-trend")
async def state_overdose_trend(
    state: str = Query(...), substance: str = Query(None),
):
    """Get overdose trend data for a state with spike detection."""
    return get_state_overdose_trend(state, substance)


@app.get("/api/public-health/national-heatmap")
async def national_heatmap():
    """Get national overdose heatmap data for choropleth."""
    return get_national_heatmap_data()


@app.get("/api/public-health/substance-breakdown")
async def substance_breakdown(state: str = Query(...)):
    """Get substance breakdown for a state."""
    return get_substance_breakdown(state)


# ─── Serve Frontend ──────────────────────────────────────

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/styles.css")
    async def serve_css():
        return FileResponse(str(FRONTEND_DIR / "styles.css"))

    @app.get("/app.js")
    async def serve_js():
        return FileResponse(str(FRONTEND_DIR / "app.js"))
