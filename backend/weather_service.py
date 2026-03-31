"""
WeatherTwin — Weather Service
Fetches current, forecast, and historical weather data from Open-Meteo (free, no API key).
"""

import httpx
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

import os

# ──────────────────────────────────────────────
# Open-Meteo API endpoints
# ──────────────────────────────────────────────
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
CURRENT_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"

# OpenWeatherMap endpoints
OWM_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"

# OpenWeather condition ID -> WMO code approximation mapping
# OWM codes: 2xx (Thunderstorm), 3xx (Drizzle), 5xx (Rain), 6xx (Snow), 7xx (Atmosphere), 800 (Clear), 80x (Clouds)
OWM_TO_WMO = {
    200: 95, 201: 96, 202: 99, 210: 95, 211: 95, 212: 99, 221: 96, 230: 95, 231: 95, 232: 99, # Thunderstorms
    300: 51, 301: 53, 302: 55, 310: 51, 311: 53, 312: 55, 313: 55, 314: 55, 321: 51, # Drizzle
    500: 61, 501: 63, 502: 65, 503: 65, 504: 65, 511: 66, 520: 80, 521: 81, 522: 82, 531: 81, # Rain
    600: 71, 601: 73, 602: 75, 611: 77, 612: 77, 613: 77, 615: 66, 616: 67, 620: 85, 621: 85, 622: 86, # Snow
    701: 45, 711: 45, 721: 45, 731: 45, 741: 45, 751: 45, 761: 45, 762: 45, 771: 45, 781: 45, # Atmospherics/Fog
    800: 0, # Clear
    801: 1, 802: 2, 803: 3, 804: 3 # Clouds
}

# WMO weather codes → human labels
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

WMO_ICONS = {
    0: "sunny", 1: "partly-cloudy", 2: "partly-cloudy", 3: "cloudy",
    45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    56: "drizzle", 57: "drizzle",
    61: "rain", 63: "rain", 65: "rain",
    66: "rain", 67: "rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "rain", 81: "rain", 82: "rain",
    85: "snow", 86: "snow",
    95: "storm", 96: "storm", 99: "storm",
}


async def geocode_city(name: str) -> Optional[dict]:
    """Resolve a city name to lat/lon + metadata."""
    # Sanitize name: remove commas which can trip up Open-Meteo geocoding
    search_name = name.replace(",", " ").strip()
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GEOCODE_URL, params={"name": search_name, "count": 5, "language": "en"})
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results")
    if not results:
        return None

    r = results[0]
    return {
        "name": r.get("name"),
        "country": r.get("country", ""),
        "admin1": r.get("admin1", ""),
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "timezone": r.get("timezone", "auto"),
        "population": r.get("population"),
        "all_results": [
            {
                "name": x.get("name"),
                "country": x.get("country", ""),
                "admin1": x.get("admin1", ""),
                "latitude": x["latitude"],
                "longitude": x["longitude"],
            }
            for x in results
        ],
    }


async def reverse_geocode(lat: float, lon: float) -> Optional[dict]:
    """Reverse-geocode coordinates to a place name using Nominatim (OSM)."""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "WeatherTwin/1.0"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        addr = data.get("address", {})
        name = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("hamlet")
            or addr.get("county")
            or addr.get("state")
            or data.get("display_name", "Unknown").split(",")[0]
        )

        return {
            "name": name,
            "country": addr.get("country", ""),
            "admin1": addr.get("state", ""),
            "latitude": float(lat),
            "longitude": float(lon),
            "timezone": "auto",
            "population": None,
            "all_results": [],
        }
    except Exception:
        # Fallback: return a basic geo dict with coordinates as name
        return {
            "name": f"{round(lat, 2)}°, {round(lon, 2)}°",
            "country": "",
            "admin1": "",
            "latitude": float(lat),
            "longitude": float(lon),
            "timezone": "auto",
            "population": None,
            "all_results": [],
        }


async def get_current_weather(lat: float, lon: float) -> dict:
    """Fetch current weather conditions using OpenWeatherMap API."""
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY clearly not found in environment variables.")

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric" # Returns temp in Celsius, wind in m/s
    }
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(OWM_CURRENT_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    # OpenWeather places weather condition info in a list 
    owm_condition_id = data["weather"][0]["id"] if "weather" in data and len(data["weather"]) > 0 else 800
    wmo_code = OWM_TO_WMO.get(owm_condition_id, 0)
    
    # Calculate precipitation (1h)
    rain = data.get("rain", {}).get("1h", 0)
    snowfall = data.get("snow", {}).get("1h", 0)
    total_precip = rain + snowfall
    
    # OWM provides wind speed in m/s natively, convert to km/h to match existing UI
    wind_kmh = round(data["wind"].get("speed", 0) * 3.6, 1)
    gusts_kmh = round(data["wind"].get("gust", 0) * 3.6, 1) if "gust" in data["wind"] else 0
    
    # Determine daylight vs night from sys sunrise/sunset times
    now_ts = data.get("dt", 0)
    sunrise = data.get("sys", {}).get("sunrise", 0)
    sunset = data.get("sys", {}).get("sunset", 0)
    is_day = 1 if sunrise <= now_ts <= sunset else 0

    return {
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "precipitation": total_precip,
        "rain": rain,
        "snowfall": snowfall,
        "cloud_cover": data["clouds"].get("all", 0),
        "wind_speed": wind_kmh,
        "wind_direction": data["wind"].get("deg", 0),
        "wind_gusts": gusts_kmh,
        "pressure": data["main"].get("pressure", 0),
        "is_day": bool(is_day),
        "weather_code": wmo_code,
        "condition": WMO_CODES.get(wmo_code, data["weather"][0]["main"] if data.get("weather") else "Unknown"),
        "icon": WMO_ICONS.get(wmo_code, "cloudy"),
        "units": {"temperature": "°C", "wind_speed": "km/h", "precipitation": "mm"},
        "time": datetime.utcfromtimestamp(now_ts).isoformat() if now_ts else datetime.utcnow().isoformat(),
    }


async def get_forecast(lat: float, lon: float, days: int = 7) -> dict:
    """Fetch hourly + daily forecast."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,apparent_temperature,is_day",
        "daily": "temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,precipitation_probability_max,weather_code,wind_speed_10m_max,sunrise,sunset,uv_index_max",
        "timezone": "auto",
        "forecast_days": min(days, 16),
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(CURRENT_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    # Process daily data
    daily_raw = data.get("daily", {})
    daily = []
    times = daily_raw.get("time", [])
    for i, t in enumerate(times):
        code = daily_raw.get("weather_code", [0] * len(times))[i]
        daily.append({
            "date": t,
            "temp_max": daily_raw.get("temperature_2m_max", [None] * len(times))[i],
            "temp_min": daily_raw.get("temperature_2m_min", [None] * len(times))[i],
            "feels_max": daily_raw.get("apparent_temperature_max", [None] * len(times))[i],
            "feels_min": daily_raw.get("apparent_temperature_min", [None] * len(times))[i],
            "precipitation": daily_raw.get("precipitation_sum", [0] * len(times))[i],
            "precip_probability": daily_raw.get("precipitation_probability_max", [0] * len(times))[i],
            "wind_max": daily_raw.get("wind_speed_10m_max", [0] * len(times))[i],
            "uv_index": daily_raw.get("uv_index_max", [0] * len(times))[i],
            "sunrise": daily_raw.get("sunrise", [None] * len(times))[i],
            "sunset": daily_raw.get("sunset", [None] * len(times))[i],
            "weather_code": code,
            "condition": WMO_CODES.get(code, "Unknown"),
            "icon": WMO_ICONS.get(code, "cloudy"),
        })

    # Process hourly (next 48h for detail)
    hourly_raw = data.get("hourly", {})
    hourly = []
    h_times = hourly_raw.get("time", [])
    for i, t in enumerate(h_times[:48]):
        code = hourly_raw.get("weather_code", [0] * len(h_times))[i]
        hourly.append({
            "time": t,
            "temperature": hourly_raw.get("temperature_2m", [None] * len(h_times))[i],
            "feels_like": hourly_raw.get("apparent_temperature", [None] * len(h_times))[i],
            "humidity": hourly_raw.get("relative_humidity_2m", [None] * len(h_times))[i],
            "precip_probability": hourly_raw.get("precipitation_probability", [0] * len(h_times))[i],
            "precipitation": hourly_raw.get("precipitation", [0] * len(h_times))[i],
            "wind_speed": hourly_raw.get("wind_speed_10m", [0] * len(h_times))[i],
            "weather_code": code,
            "is_day": bool(hourly_raw.get("is_day", [1] * len(h_times))[i]),
            "condition": WMO_CODES.get(code, "Unknown"),
            "icon": WMO_ICONS.get(code, "cloudy"),
        })

    return {"daily": daily, "hourly": hourly, "timezone": data.get("timezone", "")}


async def get_historical_summary(lat: float, lon: float, years: int = 5) -> dict:
    """
    Fetch historical weather data and compute climate statistics.
    Uses the same month window (±15 days) for context relevance.
    """
    now = datetime.utcnow()
    current_month = now.month
    current_day = now.day

    all_temps = []
    all_precip = []
    yearly_data = []

    for y in range(1, years + 1):
        year = now.year - y
        # Window: 30 days around the same date in prior years
        center = datetime(year, current_month, min(current_day, 28))
        start = center - timedelta(days=15)
        end = center + timedelta(days=15)

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
            "timezone": "auto",
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(HISTORICAL_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            daily = data.get("daily", {})
            temps_max = [t for t in daily.get("temperature_2m_max", []) if t is not None]
            temps_min = [t for t in daily.get("temperature_2m_min", []) if t is not None]
            temps_mean = [t for t in daily.get("temperature_2m_mean", []) if t is not None]
            precip = [p for p in daily.get("precipitation_sum", []) if p is not None]

            all_temps.extend(temps_mean)
            all_precip.extend(precip)

            yearly_data.append({
                "year": year,
                "avg_temp": round(float(np.mean(temps_mean)), 1) if temps_mean else None,
                "max_temp": round(float(max(temps_max)), 1) if temps_max else None,
                "min_temp": round(float(min(temps_min)), 1) if temps_min else None,
                "total_precip": round(float(sum(precip)), 1) if precip else None,
                "avg_precip": round(float(np.mean(precip)), 1) if precip else None,
            })
        except Exception:
            continue  # skip years with missing data

    if not all_temps:
        return {"error": "No historical data available", "years_analyzed": 0}

    # Compute climate normals
    temp_arr = np.array(all_temps)
    precip_arr = np.array(all_precip) if all_precip else np.array([0])

    return {
        "years_analyzed": len(yearly_data),
        "period": f"Same {30}-day window across {years} years",
        "temperature": {
            "mean": round(float(np.mean(temp_arr)), 1),
            "median": round(float(np.median(temp_arr)), 1),
            "std_dev": round(float(np.std(temp_arr)), 1),
            "record_high": round(float(np.max(temp_arr)), 1),
            "record_low": round(float(np.min(temp_arr)), 1),
            "p10": round(float(np.percentile(temp_arr, 10)), 1),
            "p90": round(float(np.percentile(temp_arr, 90)), 1),
        },
        "precipitation": {
            "avg_daily": round(float(np.mean(precip_arr)), 2),
            "max_daily": round(float(np.max(precip_arr)), 1),
            "rainy_day_pct": round(float(np.mean(precip_arr > 0.1) * 100), 1),
        },
        "yearly_breakdown": yearly_data,
        "trend": _compute_trend(yearly_data),
    }


def _compute_trend(yearly_data: list) -> dict:
    """Simple linear trend from yearly averages."""
    valid = [y for y in yearly_data if y["avg_temp"] is not None]
    if len(valid) < 3:
        return {"direction": "insufficient data", "rate_per_year": 0}

    valid.sort(key=lambda x: x["year"])
    years = np.array([y["year"] for y in valid], dtype=float)
    temps = np.array([y["avg_temp"] for y in valid], dtype=float)

    # Linear regression
    coeffs = np.polyfit(years, temps, 1)
    rate = round(float(coeffs[0]), 3)

    if abs(rate) < 0.05:
        direction = "stable"
    elif rate > 0:
        direction = "warming"
    else:
        direction = "cooling"

    return {"direction": direction, "rate_per_year_c": rate}


def compare_to_historical(current_temp: float, historical: dict) -> dict:
    """Compare current temperature to historical norms."""
    if "error" in historical or "temperature" not in historical:
        return {"status": "no historical data available"}

    h = historical["temperature"]
    mean = h["mean"]
    std = h["std_dev"]
    diff = round(current_temp - mean, 1)

    if std > 0:
        z_score = round(diff / std, 2)
    else:
        z_score = 0

    # Determine how unusual
    if abs(z_score) < 0.5:
        assessment = "typical"
        severity = "normal"
    elif abs(z_score) < 1.0:
        assessment = "slightly unusual"
        severity = "mild"
    elif abs(z_score) < 1.5:
        assessment = "unusual"
        severity = "moderate"
    elif abs(z_score) < 2.0:
        assessment = "very unusual"
        severity = "significant"
    else:
        assessment = "extremely unusual"
        severity = "extreme"

    warmer_or_cooler = "warmer" if diff > 0 else "cooler" if diff < 0 else "exactly at"

    # Percentile estimate
    if diff > 0:
        percentile = min(99, round(50 + abs(z_score) * 34, 0))
    elif diff < 0:
        percentile = max(1, round(50 - abs(z_score) * 34, 0))
    else:
        percentile = 50

    return {
        "current_temp": current_temp,
        "historical_mean": mean,
        "difference": diff,
        "z_score": z_score,
        "assessment": assessment,
        "severity": severity,
        "description": f"Current temperature is {abs(diff)}°C {warmer_or_cooler} than the historical average of {mean}°C for this time of year. This is {assessment} (z-score: {z_score}).",
        "percentile": percentile,
        "record_high": h["record_high"],
        "record_low": h["record_low"],
    }


async def fetch_full_weather_data(geo: dict, grow_api_key: str = "", user_profile: dict = None) -> dict:
    """Consolidated weather fetch including current, forecast, history and insights."""
    import llm_service as llm
    
    lat, lon = geo["latitude"], geo["longitude"]
    current = await get_current_weather(lat, lon)
    forecast = await get_forecast(lat, lon, 7)
    historical = await get_historical_summary(lat, lon, 5)
    comparison = compare_to_historical(current["temperature"], historical)

    insight = ""
    if grow_api_key and grow_api_key != "your_groq_api_key_here":
        try:
            insight = await llm.generate_proactive_insight(geo, current, historical, comparison, user_profile or {})
        except Exception as e:
            print(f"⚠️ LLM Insight failed: {e}")

    if not insight:
        insight = generate_local_insight(current, forecast)

    # Local Time
    local_time = ""
    tz_str = forecast.get("timezone", "") or geo.get("timezone", "")
    if tz_str and tz_str != "auto":
        try:
            import pytz
            from datetime import datetime
            tz = pytz.timezone(tz_str)
            loc_dt = datetime.now(tz)
            local_time = loc_dt.strftime("%H:%M · %A, %b %d")
        except Exception:
            pass

    return {
        "city": geo,
        "current": current,
        "forecast": forecast,
        "historical": historical,
        "comparison": comparison,
        "insight": insight,
        "local_time": local_time
    }


async def get_forecast_at_time(lat: float, lon: float, target_dt: "datetime") -> dict:
    """Fetch forecast data for a specific future datetime.

    Returns the hourly entry closest to *target_dt* together with the
    daily summary for that date.  Falls back to current weather when
    the target is outside the forecast window.
    """
    forecast = await get_forecast(lat, lon, days=16)

    # --- Find the closest hourly entry ---
    best_hourly = None
    best_diff = None
    for h in forecast.get("hourly", []):
        try:
            h_dt = datetime.fromisoformat(h["time"])
        except Exception:
            continue
        diff = abs((h_dt - target_dt).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_hourly = h

    # --- Find the matching daily entry ---
    target_date_str = target_dt.strftime("%Y-%m-%d")
    best_daily = None
    for d in forecast.get("daily", []):
        if d.get("date") == target_date_str:
            best_daily = d
            break

    if best_hourly:
        return {
            "temperature": best_hourly.get("temperature"),
            "feels_like": best_hourly.get("feels_like"),
            "humidity": best_hourly.get("humidity"),
            "precipitation": best_hourly.get("precipitation", 0),
            "precip_probability": best_hourly.get("precip_probability", 0),
            "wind_speed": best_hourly.get("wind_speed", 0),
            "condition": best_hourly.get("condition", "Unknown"),
            "icon": best_hourly.get("icon", "cloudy"),
            "is_day": best_hourly.get("is_day", True),
            "time": best_hourly.get("time"),
            "daily_summary": best_daily,
            "source": "forecast",
        }

    # Fallback: target is outside forecast range – return empty dict
    return {}


def generate_local_insight(current: dict, forecast: dict) -> str:
    """Rule-based clothing/activity advice."""
    temp = current.get("temperature", 20)
    feels = current.get("feels_like", temp)
    is_day = current.get("is_day", True)
    condition = current.get("condition", "").lower()
    precip = current.get("precipitation", 0)
    
    parts = []
    if feels <= 0:
        parts.append(f"At {temp}°C (feels like {feels}°C), bundle up with a heavy winter coat and layers.")
    elif feels <= 10:
        parts.append(f"Chilly {temp}°C (feels {feels}°C) — a warm jacket is recommended.")
    elif feels <= 18:
        parts.append(f"At {temp}°C, a light jacket or sweater should be enough.")
    else:
        parts.append(f"Mild {temp}°C — comfortable for light clothing.")

    if "rain" in condition or "drizzle" in condition or precip > 0:
        parts.append("Keep an umbrella handy!")
    elif "snow" in condition:
        parts.append("Watch for slippery paths.")
    
    return " ".join(parts)

