"""
Health Weather — agent tool.
"""

from agent.tools import fetch_weather, extract_city_from_query
from .service import (
    get_health_report, fetch_openmeteo_health_data, fetch_air_quality,
    compute_sad_index, compute_aq_composite, score_exercise_windows,
)


def health_weather_tool(input_text: str) -> str:
    """Agent-callable tool: returns health-weather indices and recommendation."""
    city = extract_city_from_query(input_text)
    if not city:
        city = input_text.strip()

    weather_data = fetch_weather(city)
    if "error" in weather_data:
        return f"Could not fetch weather for {city}: {weather_data['error']}"

    # Extract health condition hint from input
    conditions = ["asthma", "allergy", "migraine", "arthritis", "joint pain"]
    condition = ""
    for c in conditions:
        if c in input_text.lower():
            condition = c
            break

    report = get_health_report(city, weather_data, condition)
    idx = report.indices

    result = f"🏥 **Health Weather Index for {city}**\n\n"
    result += f"| Index | Score | Level |\n|---|---|---|\n"
    for name, val in [
        ("🌿 Allergy", idx.allergy_index),
        ("🫁 Asthma Risk", idx.asthma_risk),
        ("🧠 Migraine Trigger", idx.migraine_trigger),
        ("🌡️ Heat Stress", idx.heat_stress),
        ("❄️ Cold Exposure", idx.cold_exposure),
        ("🦴 Joint Pain", idx.joint_pain),
        ("😴 Sleep Quality", idx.sleep_quality),
    ]:
        level = "Low" if val <= 3 else ("Moderate" if val <= 6 else "High")
        if "Sleep" in name:
            level = "Good" if val >= 7 else ("Fair" if val >= 4 else "Poor")
        result += f"| {name} | {val}/10 | {level} |\n"

    result += f"\n💡 **Recommendation:** {report.recommendation}"

    # ── Enhanced: SAD Index + AQ if location has coordinates ─────
    loc = weather_data.get("location", {})
    lat = loc.get("lat")
    lon = loc.get("lon")
    if lat and lon:
        try:
            # SAD Index
            health_data = fetch_openmeteo_health_data(lat, lon)
            if "error" not in health_data:
                sad = compute_sad_index(health_data.get("daily", {}))
                result += f"\n\n🧠 **SAD Index:** {sad.sad_index}/100 ({sad.risk_level})"
                result += f"\n  Avg sunshine (14d): {sad.avg_sunshine_hrs_14d} hrs/day"
                result += f"\n  💡 {sad.recommendation}"

            # Air Quality
            aq_data = fetch_air_quality(lat, lon)
            if "error" not in aq_data:
                aq = compute_aq_composite(aq_data)
                result += f"\n\n🌬️ **Air Quality:** {aq.icon} AQI {aq.us_aqi} — {aq.tier}"
                for act in aq.activity_guidance:
                    result += f"\n  • {act}"

            # Exercise Windows
            if "error" not in health_data:
                hourly = health_data.get("hourly", {})
                windows = score_exercise_windows(hourly)
                if windows:
                    result += "\n\n🏃 **Best Exercise Windows Today:**"
                    medals = ["🥇", "🥈", "🥉"]
                    for i, w in enumerate(windows[:3]):
                        result += f"\n  {medals[i]} {w.time_label} — Score {w.score} | {w.temp_c}°C, UV {w.uv_index}"
        except Exception:
            pass  # graceful fallback — basic health data still returned

    return result
