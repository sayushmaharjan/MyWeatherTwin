"""
Extreme Weather — agent tool.
"""

from .service import get_extreme_weather_alerts


def extreme_weather_tool(city: str) -> str:
    """Agent-callable tool: returns formatted extreme weather alert summary."""
    report = get_extreme_weather_alerts(city)

    if not report.alerts:
        result = f"🌤️ **No active weather alerts for {city}.**\n\n"
        result += f"**Overall Risk:** {report.overall_risk}\n\n"
        result += f"📊 **Historical Context:** {report.historical_comparison}"
        return result

    result = f"🌪️ **Extreme Weather Report for {city}**\n"
    result += f"**Overall Risk Level:** {report.overall_risk}\n\n"

    for i, alert in enumerate(report.alerts, 1):
        result += f"### Alert #{i}: {alert.event}\n"
        result += f"- **Severity:** {alert.severity}\n"
        result += f"- **Impact Score:** {alert.impact_score}/10\n"
        result += f"- **Headline:** {alert.headline}\n"
        if alert.areas_affected:
            result += f"- **Areas:** {alert.areas_affected}\n"
        result += f"- {alert.description[:300]}\n\n"

    result += f"📊 **Historical Context:** {report.historical_comparison}"
    return result
