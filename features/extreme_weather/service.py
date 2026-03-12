"""
Extreme Weather — core business logic.
Fetches alerts, scores severity, and produces LLM-powered historical comparisons.
"""

import requests
from config import WEATHERAPI_KEY, client, MODEL
from .models import WeatherAlert, ExtremeWeatherReport


_SEVERITY_MAP = {"Unknown": 1, "Moderate": 3, "Severe": 6, "Extreme": 9}


def get_extreme_weather_alerts(city: str) -> ExtremeWeatherReport:
    """Fetch weather alerts for a city via WeatherAPI and build a report."""
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {"key": WEATHERAPI_KEY, "q": city, "days": 2, "aqi": "yes", "alerts": "yes"}

    alerts: list[WeatherAlert] = []
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()

        raw_alerts = data.get("alerts", {}).get("alert", [])
        for a in raw_alerts:
            severity = a.get("severity", "Unknown")
            alerts.append(WeatherAlert(
                event=a.get("event", "Unknown Event"),
                severity=severity,
                headline=a.get("headline", ""),
                description=a.get("desc", "")[:500],
                impact_score=_score_severity(severity, a.get("event", "")),
                areas_affected=a.get("areas", None),
            ))
    except Exception:
        pass

    # If no real alerts, generate analysis from current conditions
    overall_risk = "Low"
    if alerts:
        max_score = max(a.impact_score for a in alerts)
        overall_risk = "Extreme" if max_score >= 8 else "High" if max_score >= 5 else "Moderate"

    comparison = _generate_historical_comparison(city, alerts)

    return ExtremeWeatherReport(
        city=city,
        alerts=alerts,
        historical_comparison=comparison,
        overall_risk=overall_risk,
    )


def _score_severity(severity: str, event_type: str) -> int:
    """Compute an impact score 1–10 based on severity and event type."""
    base = _SEVERITY_MAP.get(severity, 2)
    # Boost for particularly dangerous events
    dangerous = ["tornado", "hurricane", "typhoon", "tsunami", "blizzard"]
    if any(d in event_type.lower() for d in dangerous):
        base = min(10, base + 2)
    return base


def _generate_historical_comparison(city: str, alerts: list[WeatherAlert]) -> str:
    """Use the LLM to compare current alerts to historical patterns."""
    if not alerts:
        alert_summary = "No current alerts."
    else:
        alert_summary = "; ".join(f"{a.event} ({a.severity})" for a in alerts)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a meteorologist. Provide a brief 2-3 sentence historical comparison."},
                {"role": "user", "content": f"Current alerts for {city}: {alert_summary}. How does this compare to historical patterns for this region and season? Be specific with statistics if possible."},
            ],
            temperature=0.5,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Historical comparison unavailable."
