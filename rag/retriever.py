"""
Retriever — builds context from historical weather data for RAG.
"""

import pandas as pd


def create_weather_context(df: pd.DataFrame, city: str, limit: int = 20):
    """
    Create context from historical weather data for a specific city.
    Returns (context_string, stats_dict) or (None, None) if no data is found.
    """
    city_data = df[df["city"].str.lower() == city.lower()]

    if city_data.empty:
        return None, None

    recent_data = city_data.tail(limit)

    # Build context string
    context_parts = []
    for _, row in recent_data.iterrows():
        context_parts.append(
            f"{row.get('condition', 'Unknown')}, {row.get('temperature', 0):.1f}°C, "
            f"{row.get('humidity', 0):.0f}% humidity, {row.get('wind_speed', 0):.1f} km/h wind"
        )

    context = "; ".join(context_parts)

    # Calculate statistics
    stats = {
        "avg_temp": recent_data["temperature"].mean(),
        "avg_wind": recent_data["wind_speed"].mean(),
        "common_condition": (
            recent_data["condition"].mode()[0]
            if not recent_data["condition"].mode().empty
            else "N/A"
        ),
        "max_temp": recent_data["temperature"].max(),
        "min_temp": recent_data["temperature"].min(),
        "records_count": len(recent_data),
    }

    return context, stats
