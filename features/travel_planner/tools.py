"""
Travel Planner — agent tool.
"""

from agent.tools import extract_city_from_query
from .service import get_travel_report


def travel_planner_tool(input_text: str) -> str:
    """Agent-callable tool: returns travel weather planning report."""
    city = extract_city_from_query(input_text)
    if not city:
        city = input_text.strip()

    # Extract month
    months = ["january","february","march","april","may","june","july","august","september","october","november","december"]
    month = ""
    for m in months:
        if m in input_text.lower():
            month = m.title()
            break

    report = get_travel_report(city, month)

    result = f"✈️ **Travel Weather Report: {city}**"
    if report.month:
        result += f" ({report.month})"
    result += "\n\n"
    result += f"**🌤️ Destination Profile:**\n{report.profile}\n\n"
    result += f"**🎒 Packing List:**\n{report.packing_list}\n\n"
    result += f"**🔄 Weather Twin:** {report.weather_twin}\n\n"
    result += f"**✈️ Flight Disruption Risk:** {report.flight_risk}"
    return result
