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
