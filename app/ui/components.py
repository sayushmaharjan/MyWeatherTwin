"""
Reusable UI components — icon mapping, forecast dock, chat bubbles.
"""

from datetime import datetime


def weather_to_icon(condition: str, dt: datetime, sunrise: datetime, sunset: datetime) -> str:
    """Map a weather condition string + time of day to an emoji icon."""
    condition = condition.lower()
    is_day = sunrise <= dt <= sunset

    if "sun" in condition or "clear" in condition:
        return "☀️" if is_day else "🌙"
    elif "cloud" in condition or "overcast" in condition:
        return "☁️" if is_day else "🌥️"
    elif "rain" in condition or "drizzle" in condition:
        return "🌧️"
    elif "snow" in condition or "sleet" in condition:
        return "❄️"
    elif "storm" in condition or "thunder" in condition:
        return "⛈️"
    elif "fog" in condition or "mist" in condition:
        return "🌫️"
    elif "wind" in condition:
        return "💨"
    else:
        return "🌡️"


def condition_icon_simple(condition: str) -> str:
    """Simplified icon mapping (no day/night distinction)."""
    cond_l = condition.lower()
    if "sun" in cond_l or "clear" in cond_l:
        return "☀️"
    elif "rain" in cond_l or "drizzle" in cond_l:
        return "🌧️"
    elif "cloud" in cond_l or "overcast" in cond_l:
        return "☁️"
    elif "snow" in cond_l:
        return "❄️"
    elif "storm" in cond_l or "thunder" in cond_l:
        return "⛈️"
    else:
        return "🌤️"
