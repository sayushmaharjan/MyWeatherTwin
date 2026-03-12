"""
Health Weather — core business logic.
Computes health indices from weather data and generates recommendations via LLM.
"""

from config import client, MODEL
from .models import HealthIndices, HealthReport


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
