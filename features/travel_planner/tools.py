"""
Travel Planner — agent tools.
"""

from agent.tools import extract_city_from_query
from .service import (
    get_travel_report, fetch_road_weather, compute_road_conditions,
    compute_flight_delay,
)


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

    # Detect travel mode
    travel_mode = "Car" if any(w in input_text.lower() for w in ["car", "drive", "driving", "road trip"]) else "Flight"

    report = get_travel_report(
        destination=city,
        month=month,
        travel_mode=travel_mode,
    )

    result = f"✈️ **Travel Weather Report: {city}**"
    if report.month:
        result += f" ({report.month})"
    result += f" — {report.travel_mode}\n\n"
    result += f"**🌤️ Destination Profile:**\n{report.profile}\n\n"
    result += f"**🎒 Packing List:**\n{report.packing_list}\n\n"
    result += f"**🗺️ Itinerary:**\n{report.itinerary}\n\n"
    result += f"**🔄 Weather Diff:** {report.weather_diff}\n\n"
    risk_label = "🚗 Driving Risk" if report.travel_mode == "Car" else "✈️ Flight Risk"
    result += f"**{risk_label}:** {report.flight_risk}"

    # ── Enhanced: Road conditions if driving-related query ──
    if any(w in input_text.lower() for w in ["road", "ice", "fog", "black ice", "drive", "driving"]):
        try:
            from agent.tools import fetch_weather
            weather_data = fetch_weather(city)
            loc = weather_data.get("location", {})
            lat, lon = loc.get("lat"), loc.get("lon")
            if lat and lon:
                road_data = fetch_road_weather(lat, lon)
                road = compute_road_conditions(road_data)
                if road.current:
                    result += f"\n\n🧊 **Road Conditions Now:**"
                    result += f"\n  {road.current.ice.icon} {road.current.ice.condition}"
                    result += f" | Surface: {road.current.ice.surface_temp_c}°C"
                    result += f"\n  {road.current.fog.icon} Visibility: {road.current.fog.visibility_m}m ({road.current.fog.density})"
                    if road.current.ice.risk_factors:
                        for f in road.current.ice.risk_factors:
                            result += f"\n  • {f}"
                    result += f"\n  Safe hours in next 24h: {road.safe_hours_count}/24"
        except Exception:
            pass

    # ── Enhanced: Flight delay if flight-related query ──
    if any(w in input_text.lower() for w in ["flight", "delay", "airport", "fly"]):
        # Try to extract ICAO codes
        COMMON_AIRPORTS = {
            "chicago": "KORD", "new york": "KJFK", "jfk": "KJFK",
            "los angeles": "KLAX", "lax": "KLAX", "dallas": "KDFW",
            "atlanta": "KATL", "denver": "KDEN", "san francisco": "KSFO",
            "miami": "KMIA", "seattle": "KSEA", "boston": "KBOS",
        }
        dest_icao = None
        for name, code in COMMON_AIRPORTS.items():
            if name in input_text.lower() or name in city.lower():
                dest_icao = code
                break
        if dest_icao:
            try:
                flight = compute_flight_delay("KJFK", dest_icao)  # Default origin JFK
                result += f"\n\n✈️ **Flight Delay Risk ({dest_icao}):**"
                result += f"\n  {flight.destination.risk_level} (Score: {flight.destination.delay_risk_score}/100)"
                for reason in flight.destination.delay_reasons:
                    result += f"\n  • {reason}"
                if not flight.destination.delay_reasons:
                    result += "\n  ✅ No significant weather delays expected"
            except Exception:
                pass

    return result
