"""
Health Weather — agent tool.
"""

from agent.tools import fetch_weather, extract_city_from_query
from .service import get_health_report


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
    return result
