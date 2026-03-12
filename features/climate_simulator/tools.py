"""
Climate Simulator — agent tool.
"""

from agent.tools import extract_city_from_query
from .service import simulate_climate_scenario


def climate_simulator_tool(input_text: str) -> str:
    """Agent-callable tool: returns climate change projection."""
    city = extract_city_from_query(input_text)
    if not city:
        city = input_text.strip()

    # Extract year
    year = 2050
    for y in ["2030", "2040", "2050", "2060", "2070", "2080", "2090", "2100"]:
        if y in input_text:
            year = int(y)
            break

    # Extract scenario
    scenario = "SSP2-4.5"
    for s in ["SSP1-2.6", "SSP2-4.5", "SSP3-7.0", "SSP5-8.5"]:
        if s in input_text.upper():
            scenario = s
            break

    projection = simulate_climate_scenario(city, scenario, year)

    result = f"🧬 **Climate Projection for {city} in {year}**\n"
    result += f"**Scenario:** {scenario}\n\n"
    result += f"📊 **Key Changes:**\n"
    result += f"- **Avg High Temp Change:** {projection.avg_high_change}\n"
    result += f"- **Extreme Heat Days:** {projection.extreme_heat_days}\n\n"
    result += f"🏙️ **Climate Analog:** {projection.analog_city}\n\n"
    result += f"📖 **Narrative:** {projection.narrative}\n\n"
    result += f"⚡ **Key Impacts:** {projection.key_impacts}"
    return result
