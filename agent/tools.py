"""
Weather tool implementations the LLM agent can call.
Includes weather data retrieval, parsing, BERT prediction, and city extraction.
"""

import re
import requests
import pandas as pd
from datetime import datetime, timedelta

from config import WEATHERAPI_KEY


# ── Weather API Calls ──────────────────────────────────

def get_weather(city: str) -> str:
    """Fetch current weather summary for a city (used by the agent loop)."""
    url = "http://api.weatherapi.com/v1/current.json"
    params = {"key": WEATHERAPI_KEY, "q": city, "aqi": "no"}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        description = data["current"]["condition"]["text"]
        temperature = data["current"]["temp_c"]
        humidity = data["current"]["humidity"]
        feels_like = data["current"]["feelslike_c"]
        wind_kph = data["current"]["wind_kph"]

        return (
            f"Current weather in {city}: {description}. "
            f"Temperature: {temperature}°C (feels like {feels_like}°C), "
            f"Humidity: {humidity}%, Wind: {wind_kph} km/h"
        )
    except requests.exceptions.HTTPError:
        return f"Error: Could not find weather for '{city}'."
    except Exception as e:
        return f"Error fetching weather data: {str(e)}"


def get_quick_weather(city: str) -> dict:
    """Get quick weather data for map markers."""
    try:
        url = "http://api.weatherapi.com/v1/current.json"
        params = {"key": WEATHERAPI_KEY, "q": city, "aqi": "no"}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        return {
            "temp": data["current"]["temp_c"],
            "condition": data["current"]["condition"]["text"],
            "humidity": data["current"]["humidity"],
            "wind": data["current"]["wind_kph"],
        }
    except Exception:
        return {"temp": "N/A", "condition": "N/A", "humidity": "N/A", "wind": "N/A"}


def fetch_weather(city: str):
    """Fetch full forecast data for a city (2 days, AQI enabled)."""
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {"key": WEATHERAPI_KEY, "q": city, "days": 2, "aqi": "yes"}
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}


def fetch_weather_by_coords(lat: float, lon: float):
    """Fetch weather data using latitude and longitude."""
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {"key": WEATHERAPI_KEY, "q": f"{lat},{lon}", "days": 2, "aqi": "yes"}
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}


# ── Response Parsers ───────────────────────────────────

def parse_current(data):
    """Parse current weather from API response into a flat dict."""
    cur = data["current"]
    loc = data["location"]
    return {
        "city": loc["name"],
        "region": loc["region"],
        "country": loc.get("country", ""),
        "lat": loc.get("lat", 0),
        "lon": loc.get("lon", 0),
        "localtime": loc["localtime"],
        "temp_c": cur["temp_c"],
        "condition": cur["condition"]["text"],
        "humidity": cur["humidity"],
        "wind_kph": cur["wind_kph"],
        "pressure_mb": cur["pressure_mb"],
        "vis_km": cur["vis_km"],
        "uv": cur["uv"],
        "aqi": cur.get("air_quality", {}).get("us-epa-index", "N/A"),
        "sunrise": data["forecast"]["forecastday"][0]["astro"]["sunrise"],
        "sunset": data["forecast"]["forecastday"][0]["astro"]["sunset"],
    }


def get_24h_data(data, weather_to_icon_fn=None):
    """
    Parse next-12-hour forecast from API response.
    Returns (times_12h, temps_12h, humidity_12h, conditions_12h).
    """
    current_time_str = data["location"]["localtime"]
    current_time = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M")

    hours = data["forecast"]["forecastday"][0]["hour"]

    times_12h = []
    temps_12h = []
    humidity_12h = []
    conditions_12h = []

    for h in hours:
        h_time = datetime.strptime(h["time"], "%Y-%m-%d %H:%M")
        if current_time <= h_time <= current_time + timedelta(hours=12):
            times_12h.append(h_time.strftime("%H:%M"))
            temps_12h.append(h["temp_c"])
            cond = h["condition"]["text"]
            conditions_12h.append(cond)

    return times_12h, temps_12h, humidity_12h, conditions_12h


# ── City Extraction ────────────────────────────────────

def extract_city_from_query(query: str) -> str:
    """Extract city name from user query using pattern matching."""
    common_cities = [
        "new york", "london", "tokyo", "paris", "sydney", "berlin",
        "rome", "madrid", "beijing", "moscow", "dubai", "singapore",
        "los angeles", "chicago", "toronto", "mumbai", "delhi",
        "bangkok", "hong kong", "seoul", "amsterdam", "barcelona",
        "san diego", "san francisco",
    ]

    query_lower = query.lower()

    for city in common_cities:
        if city in query_lower:
            return city.title()

    # Fallback: regex after prepositions
    match = re.search(r"(?:in|at|for)\s+([a-z\s]+)", query_lower)
    if match:
        city_candidate = match.group(1).strip()
        city_candidate = re.sub(
            r"\b(summer|winter|spring|fall|today|tomorrow)\b", "", city_candidate
        )
        return city_candidate.strip().title()

    return None


# ── BERT Prediction ────────────────────────────────────

def predict_weather_with_bert(query: str, weather_df: pd.DataFrame, classifier):
    """Use BERT to classify and predict weather based on historical data."""
    from rag.retriever import create_weather_context

    try:
        city = extract_city_from_query(query)

        if not city:
            return None, "Could not identify city in query. Please mention a city name."

        context, stats = create_weather_context(weather_df, city)

        if not context or not stats:
            return None, f"No historical data found for {city}. Try using Live Weather mode."

        prediction_input = (
            f"Weather forecast for {city}: Based on recent patterns showing {context}"
        )

        result = classifier(prediction_input[:512])

        predicted_class = result[0]["label"]
        confidence = result[0]["score"]

        forecast = f"""
🔮 **Weather Forecast for {city}** (AI-Powered Prediction)

🤖 **BERT Model Prediction:** 
- **Condition:** {predicted_class}
- **Confidence:** {confidence * 100:.1f}%

📊 **Statistical Analysis** (Based on {stats['records_count']} recent records):
- **Average Temperature:** {stats['avg_temp']:.1f}°C
- **Temperature Range:** {stats['min_temp']:.1f}°C to {stats['max_temp']:.1f}°C

- **Average Wind Speed:** {stats['avg_wind']:.1f} km/h
- **Most Common Condition:** {stats['common_condition']}

🎯 **Forecast Summary:**
Expect weather conditions similar to recent patterns. The AI model predicts **{predicted_class}** 
with {confidence * 100:.1f}% confidence based on historical data analysis.

⚠️ *This prediction is based on historical patterns and AI classification.*
"""
        return forecast, None

    except Exception as e:
        return None, f"BERT prediction error: {str(e)}"
