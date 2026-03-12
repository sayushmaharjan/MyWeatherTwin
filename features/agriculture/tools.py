"""
Agriculture — agent tool.
"""

from agent.tools import fetch_weather, extract_city_from_query
from .service import get_agriculture_report


def agriculture_tool(input_text: str) -> str:
    """Agent-callable tool: returns agricultural weather intelligence."""
    city = extract_city_from_query(input_text)
    if not city:
        city = input_text.strip()

    # Try to extract crop name
    crops = ["tomato", "corn", "wheat", "rice", "soybean", "lettuce", "pepper", "potato", "strawberry"]
    crop = ""
    for c in crops:
        if c in input_text.lower():
            crop = c.title()
            break

    weather_data = fetch_weather(city)
    if "error" in weather_data:
        return f"Could not fetch weather for {city}: {weather_data['error']}"

    report = get_agriculture_report(city, weather_data, crop)

    result = f"🌾 **Agricultural Weather Intelligence for {city}**\n\n"
    if report.crop:
        result += f"🌱 **Crop:** {report.crop}\n\n"
    result += f"| Metric | Value |\n|---|---|\n"
    result += f"| 🌡️ Growing Degree Days | {report.gdd} |\n"
    result += f"| ❄️ Frost Risk | {report.frost_risk_pct}% |\n"
    result += f"| 💧 Soil Moisture | {report.soil_moisture_est} |\n"
    if report.planting_window:
        result += f"| 📅 Planting Window | {report.planting_window} |\n"
    result += f"\n🧑‍🌾 **Advice:** {report.advice}"
    return result
