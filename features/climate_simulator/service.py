"""
Climate Simulator — core business logic.
Generates IPCC-style climate projections and future narratives via LLM.
"""

import json
from config import client, MODEL
from .models import ClimateProjection


SCENARIOS = {
    "SSP1-2.6": "Low emissions — sustainable path",
    "SSP2-4.5": "Moderate emissions — middle of the road",
    "SSP3-7.0": "High emissions — regional rivalry",
    "SSP5-8.5": "Very high emissions — fossil-fueled development",
}


def simulate_climate_scenario(city: str, scenario: str = "SSP2-4.5", year: int = 2050) -> ClimateProjection:
    """Generate a climate projection for a city under a given IPCC scenario and year."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a climate scientist. Generate a climate projection as JSON: "
                    "{\"avg_high_change\": str (e.g. '+4°F'), \"extreme_heat_days\": str (e.g. '8/yr → 24/yr'), "
                    "\"analog_city\": str (present-day city that matches projected climate), "
                    "\"narrative\": str (max 300 chars, describe what living there will feel like), "
                    "\"key_impacts\": str (max 200 chars, energy/water/health impacts)}. "
                    "Use IPCC CMIP6 knowledge. Reply ONLY with JSON."
                )},
                {"role": "user", "content": f"Project climate for {city} in {year} under {scenario} ({SCENARIOS.get(scenario, '')})."},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        data = json.loads(text)
        return ClimateProjection(city=city, scenario=scenario, year=year, **data)
    except Exception:
        return ClimateProjection(
            city=city, scenario=scenario, year=year,
            narrative="Climate projection unavailable.",
            analog_city="Unknown",
        )
