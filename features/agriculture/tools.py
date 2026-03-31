"""
Agriculture — agent tool.
"""

from agent.tools import fetch_weather, extract_city_from_query
from .service import (
    get_agriculture_report, fetch_agriculture_data,
    compute_irrigation_schedule, compute_livestock_heat_stress,
    compute_disease_risk, CROP_KC,
)


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

    # ── Enhanced: Irrigation + THI + Disease if we have coords ──
    loc = weather_data.get("location", {})
    lat = loc.get("lat")
    lon = loc.get("lon")
    if lat and lon:
        try:
            ag_data = fetch_agriculture_data(lat, lon)
            if "error" not in ag_data:
                # Irrigation
                irr_crop = crop.lower() if crop.lower() in CROP_KC else "corn"
                irr = compute_irrigation_schedule(ag_data, irr_crop)
                if irr.next_irrigation:
                    nxt = irr.next_irrigation
                    result += f"\n\n💧 **Irrigation Alert:** Next irrigation on **{nxt.date}** — {nxt.deficit_mm}mm deficit ({nxt.water_needed_liters:,} liters)"
                else:
                    result += "\n\n💧 **Irrigation:** No irrigation needed this week."

                # THI
                thi = compute_livestock_heat_stress(ag_data)
                result += f"\n\n🐄 **Livestock THI:** {thi.current_thi} ({thi.current_level})"
                if thi.danger_hours_count > 0:
                    result += f" — ⚠️ {thi.danger_hours_count} danger hours in next 24hrs"

                # Disease
                all_crops = ["corn", "wheat", "soybeans", "tomatoes", "potatoes"]
                diseases = compute_disease_risk(ag_data, all_crops)
                if diseases:
                    result += "\n\n🦠 **Disease Alerts:**"
                    for d in diseases[:3]:
                        result += f"\n  • {d.disease} — Risk {d.risk_percent}% ({d.severity})"
        except Exception:
            pass

    return result
