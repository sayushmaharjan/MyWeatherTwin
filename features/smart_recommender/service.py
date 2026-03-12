"""
Smart Recommender — core business logic.
Generates outfit, exercise, commute, food, photo, and activity recommendations via LLM.
"""

import json
from config import client, MODEL
from .models import Recommendations


def get_smart_recommendations(city: str, weather_data: dict) -> Recommendations:
    """Generate all 6 recommendation categories from weather data."""
    cur = weather_data.get("current", {})
    condition = cur.get("condition", {}).get("text", "Unknown")
    temp_c = cur.get("temp_c", 20)
    humidity = cur.get("humidity", 50)
    wind_kph = cur.get("wind_kph", 10)
    uv = cur.get("uv", 3)
    vis_km = cur.get("vis_km", 10)

    weather_summary = (
        f"City: {city}. Temp: {temp_c}°C, Condition: {condition}, "
        f"Humidity: {humidity}%, Wind: {wind_kph} km/h, UV: {uv}, Visibility: {vis_km} km."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a lifestyle advisor. Given weather, provide recommendations as JSON: "
                    "{\"outfit\": str (max 100 chars), \"exercise\": str (max 100 chars), "
                    "\"commute\": str (max 100 chars), \"food\": str (max 80 chars), "
                    "\"photo_tip\": str (max 100 chars), \"activity\": str (max 100 chars)}. "
                    "Reply ONLY with JSON."
                )},
                {"role": "user", "content": f"Weather: {weather_summary}"},
            ],
            temperature=0.7,
            max_tokens=350,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        data = json.loads(text)
        return Recommendations(city=city, **data)
    except Exception:
        return Recommendations(
            city=city,
            outfit="Dress comfortably for the weather.",
            exercise="Check conditions before heading out.",
            commute="Normal commute expected.",
            food="Enjoy a meal suited to the temperature.",
            photo_tip="Look for interesting lighting.",
            activity="Enjoy your day!",
        )
