"""
Smart Recommender — agent tool.
"""

from agent.tools import fetch_weather, extract_city_from_query
from .service import get_smart_recommendations


def smart_recommender_tool(input_text: str) -> str:
    """Agent-callable tool: returns smart weather-based recommendations."""
    city = extract_city_from_query(input_text)
    if not city:
        city = input_text.strip()

    weather_data = fetch_weather(city)
    if "error" in weather_data:
        return f"Could not fetch weather for {city}: {weather_data['error']}"

    recs = get_smart_recommendations(city, weather_data)

    result = f"🔔 **Smart Recommendations for {city}**\n\n"
    result += f"👔 **Outfit:** {recs.outfit}\n\n"
    result += f"🏃 **Exercise:** {recs.exercise}\n\n"
    result += f"🚗 **Commute:** {recs.commute}\n\n"
    result += f"🍽️ **Food:** {recs.food}\n\n"
    result += f"📸 **Photo Tip:** {recs.photo_tip}\n\n"
    result += f"🌅 **Activity:** {recs.activity}"
    return result
