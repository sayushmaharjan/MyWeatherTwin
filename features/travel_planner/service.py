"""
Travel Planner — core business logic.
Destination profiles, packing lists, weather twin matching, flight risk via LLM.
"""

from config import client, MODEL
from .models import TravelReport


def get_travel_report(destination: str, month: str = "") -> TravelReport:
    """Generate a comprehensive travel weather report."""
    profile = _get_destination_profile(destination, month)
    packing = _get_packing_list(destination, month)
    twin = _find_weather_twin(destination, month)
    flight_risk = _assess_flight_risk(destination, month)

    return TravelReport(
        destination=destination,
        month=month,
        profile=profile,
        packing_list=packing,
        weather_twin=twin,
        flight_risk=flight_risk,
    )


def _get_destination_profile(destination: str, month: str) -> str:
    """LLM-generated destination weather profile."""
    month_info = f" in {month}" if month else ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a travel weather expert. Give a brief destination weather profile (max 400 chars) with averages, rain days, and best tips."},
                {"role": "user", "content": f"What's the weather like in {destination}{month_info}? Include avg highs/lows, rain days, and one key tip."},
            ],
            temperature=0.6,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Destination profile unavailable."


def _get_packing_list(destination: str, month: str) -> str:
    """LLM-generated packing recommendations."""
    month_info = f" in {month}" if month else ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a travel packing advisor. Give a concise packing list (max 300 chars) based on typical weather."},
                {"role": "user", "content": f"What should I pack for {destination}{month_info}?"},
            ],
            temperature=0.6,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Packing list unavailable."


def _find_weather_twin(destination: str, month: str) -> str:
    """Find a 'weather twin' city using LLM knowledge."""
    month_info = f" in {month}" if month else ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a climatologist. Name ONE city whose current weather is most similar to the given destination's weather in the given period. Reply in format: 'CityName — brief reason (1 sentence)'."},
                {"role": "user", "content": f"What city has weather most similar to {destination}{month_info}?"},
            ],
            temperature=0.5,
            max_tokens=80,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Weather twin unavailable."


def _assess_flight_risk(destination: str, month: str) -> str:
    """Assess flight disruption risk via LLM."""
    month_info = f" in {month}" if month else ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an aviation weather expert. Rate flight disruption risk as Low, Moderate, or High with a brief 1-sentence reason. Max 100 chars."},
                {"role": "user", "content": f"Flight disruption risk for travel to {destination}{month_info}?"},
            ],
            temperature=0.3,
            max_tokens=60,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Low"
