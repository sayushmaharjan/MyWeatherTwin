"""
Agriculture — core business logic.
GDD calculation, frost risk, soil moisture estimation, and LLM planting advice.
"""

from config import client, MODEL
from .models import AgriculturalReport


def compute_growing_degree_days(temp_c: float, base_temp: float = 10.0) -> float:
    """Compute GDD contribution for a single day. base_temp defaults to 10°C."""
    return max(0, temp_c - base_temp)


def estimate_frost_risk(temp_c: float, wind_kph: float, humidity: int) -> int:
    """Estimate frost risk percentage from current conditions."""
    if temp_c > 5:
        return 0
    risk = max(0, int((5 - temp_c) * 15))
    if wind_kph < 5:
        risk += 10  # still air = more frost
    if humidity > 80:
        risk += 5
    return min(100, risk)


def estimate_soil_moisture(temp_c: float, precip_mm: float, humidity: int) -> str:
    """Simple soil moisture estimation."""
    if precip_mm > 10:
        return "Wet"
    elif precip_mm > 2:
        return "Moist"
    elif temp_c > 30 and humidity < 30:
        return "Dry"
    else:
        return "Normal"


def get_agriculture_report(city: str, weather_data: dict, crop: str = "") -> AgriculturalReport:
    """Generate a full agricultural weather report."""
    cur = weather_data.get("current", {})
    temp_c = cur.get("temp_c", 20)
    wind_kph = cur.get("wind_kph", 10)
    humidity = cur.get("humidity", 50)
    precip_mm = cur.get("precip_mm", 0)

    gdd = compute_growing_degree_days(temp_c)
    frost_risk = estimate_frost_risk(temp_c, wind_kph, humidity)
    soil_moisture = estimate_soil_moisture(temp_c, precip_mm, humidity)
    advice, planting_window = _get_planting_advice(city, crop, temp_c, frost_risk)

    return AgriculturalReport(
        city=city,
        gdd=round(gdd, 1),
        frost_risk_pct=frost_risk,
        soil_moisture_est=soil_moisture,
        planting_window=planting_window,
        advice=advice,
        crop=crop or None,
    )


def _get_planting_advice(city: str, crop: str, temp_c: float, frost_risk: int) -> tuple[str, str]:
    """Use LLM to generate planting advice and window."""
    crop_info = f" for {crop}" if crop else ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an agricultural advisor. Give brief planting advice (max 400 chars). Include a recommended planting window on the last line prefixed with 'WINDOW:'."},
                {"role": "user", "content": f"City: {city}. Current temp: {temp_c}°C. Frost risk: {frost_risk}%. Give planting advice{crop_info}."},
            ],
            temperature=0.5,
            max_tokens=200,
        )
        text = response.choices[0].message.content.strip()
        # Extract planting window
        lines = text.split("\n")
        window = ""
        advice_lines = []
        for line in lines:
            if line.strip().upper().startswith("WINDOW:"):
                window = line.split(":", 1)[1].strip()
            else:
                advice_lines.append(line)
        return "\n".join(advice_lines), window
    except Exception:
        return "Planting advice unavailable.", ""
