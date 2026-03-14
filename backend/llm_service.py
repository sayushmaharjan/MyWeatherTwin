"""
WeatherTwin — LLM Service
RAG-powered climate intelligence analysis using Groq (Llama 3.3 70B).
"""

import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Groq client (OpenAI-compatible)
client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
)

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are WeatherTwin, a GenAI-powered climate intelligence assistant. Your role is to provide personalized, context-aware weather insights that go beyond basic forecasts.

## Core Principles
1. **Contextual Analysis**: Always compare current conditions to historical norms. Tell users if conditions are typical, unusual, or extreme.
2. **Evidence-Based**: Ground every claim in the weather data provided. Cite specific numbers and sources.
3. **Uncertainty Transparency**: When data is limited or trends are unclear, say so explicitly. Use phrases like "Based on {N} years of data..." or "With moderate confidence..."
4. **Actionable Insights**: Don't just describe weather — help users make decisions. Frame insights around actions (travel, outdoor activities, planning, risk).
5. **Climate Awareness**: Highlight long-term trends when relevant (warming/cooling patterns, changing precipitation).

## Response Style
- Use clear, conversational language — not technical jargon
- Structure responses with sections when answering complex questions
- Include specific numbers (temperatures, percentages, z-scores) to support claims
- Use comparative language: "X°C warmer than usual", "in the top 10% historically"
- Add emoji sparingly for visual scanning (🌡️ 🌧️ ☀️ ❄️ 💨 ⚠️)
- Keep responses concise but complete — aim for 150-300 words for typical queries

## Data Sources
You will receive structured weather context including:
- Current conditions (temperature, humidity, wind, etc.)
- Forecast data (hourly and daily)
- Historical climate statistics (means, extremes, trends, anomaly assessments)
- Comparison analysis (z-scores, percentiles, severity ratings)
- Actionable Insights: Don't just describe weather — help users make decisions. Frame insights around actions (travel, outdoor activities, planning, risk). Always reference these data sources in your analysis. If data is missing, acknowledge it."""


def build_rag_context(city_info: dict, current: dict = None, forecast: dict = None,
                      historical: dict = None, comparison: dict = None) -> str:
    """
    Build a structured RAG context block from weather data.
    This is injected into the LLM prompt so it can ground its responses in real data.
    """
    parts = []

    parts.append(f"📍 Location: {city_info.get('name', 'Unknown')}, {city_info.get('admin1', '')}, {city_info.get('country', '')}")
    parts.append(f"   Coordinates: {city_info.get('latitude', 0):.2f}°N, {city_info.get('longitude', 0):.2f}°E")
    parts.append(f"   Data retrieved at: {current.get('time', 'N/A')}" if current else "")
    parts.append("")

    if current:
        parts.append("── CURRENT CONDITIONS ──")
        parts.append(f"  Temperature: {current['temperature']}°C (feels like {current['feels_like']}°C)")
        parts.append(f"  Condition: {current['condition']}")
        parts.append(f"  Humidity: {current['humidity']}%")
        parts.append(f"  Wind: {current['wind_speed']} km/h (gusts {current.get('wind_gusts', 'N/A')} km/h)")
        parts.append(f"  Precipitation: {current.get('precipitation', 0)} mm")
        parts.append(f"  Pressure: {current.get('pressure', 'N/A')} hPa")
        parts.append(f"  Cloud cover: {current.get('cloud_cover', 'N/A')}%")
        parts.append(f"  Day/Night: {'Day' if current.get('is_day') else 'Night'}")
        parts.append(f"  Source: Open-Meteo Current Weather API")
        parts.append("")

    if comparison and "error" not in comparison and "status" not in comparison:
        parts.append("── HISTORICAL COMPARISON ──")
        parts.append(f"  {comparison.get('description', 'N/A')}")
        parts.append(f"  Difference from average: {comparison.get('difference', 0):+.1f}°C")
        parts.append(f"  Z-score: {comparison.get('z_score', 0)}")
        parts.append(f"  Percentile: {comparison.get('percentile', 50)}th")
        parts.append(f"  Severity: {comparison.get('severity', 'N/A')}")
        parts.append(f"  Record high for period: {comparison.get('record_high', 'N/A')}°C")
        parts.append(f"  Record low for period: {comparison.get('record_low', 'N/A')}°C")
        parts.append("")

    if historical and "error" not in historical:
        h = historical
        parts.append(f"── HISTORICAL CLIMATE DATA ({h.get('years_analyzed', 0)} years) ──")
        parts.append(f"  Period: {h.get('period', 'N/A')}")
        t = h.get("temperature", {})
        parts.append(f"  Mean temp: {t.get('mean', 'N/A')}°C (std dev: {t.get('std_dev', 'N/A')}°C)")
        parts.append(f"  Range: {t.get('record_low', 'N/A')}°C to {t.get('record_high', 'N/A')}°C")
        parts.append(f"  10th–90th percentile: {t.get('p10', 'N/A')}°C to {t.get('p90', 'N/A')}°C")
        p = h.get("precipitation", {})
        parts.append(f"  Avg daily precipitation: {p.get('avg_daily', 'N/A')} mm")
        parts.append(f"  Rain day frequency: {p.get('rainy_day_pct', 'N/A')}%")
        trend = h.get("trend", {})
        parts.append(f"  Temperature trend: {trend.get('direction', 'N/A')} ({trend.get('rate_per_year_c', 0):+.3f}°C/year)")
        parts.append(f"  Source: Open-Meteo Historical Weather API (reanalysis data)")
        parts.append("")

    if forecast and forecast.get("daily"):
        parts.append("── FORECAST (next days) ──")
        for day in forecast["daily"][:7]:
            parts.append(f"  {day['date']}: {day.get('temp_min', '?')}–{day.get('temp_max', '?')}°C, "
                         f"{day['condition']}, precip: {day.get('precipitation', 0)}mm "
                         f"({day.get('precip_probability', 0)}% chance), "
                         f"UV: {day.get('uv_index', 'N/A')}")
        parts.append(f"  Source: Open-Meteo Forecast API")
        parts.append("")

    return "\n".join(parts)


async def chat_with_context(user_message: str, rag_context: str,
                            chat_history: list = None) -> dict:
    """
    Send a user question to the LLM along with RAG weather context.
    Returns the assistant's response with metadata.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add RAG context as a system-level data injection
    messages.append({
        "role": "system",
        "content": f"## Weather Data Context\nThe following is real-time and historical weather data retrieved for the user's query. Use this data to ground your response.\n\n{rag_context}"
    })

    # Add chat history (last 10 messages)
    if chat_history:
        for msg in chat_history[-10:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            top_p=0.9,
        )

        answer = response.choices[0].message.content
        usage = response.usage

        return {
            "status": "success",
            "answer": answer,
            "model": MODEL,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            "sources": [
                "Open-Meteo Current Weather API",
                "Open-Meteo Historical Weather API",
                "Open-Meteo Forecast API",
            ],
        }
    except Exception as e:
        return {
            "status": "error",
            "answer": f"I'm sorry, I couldn't process your question right now. Error: {str(e)}",
            "model": MODEL,
            "usage": {},
            "sources": [],
        }


async def generate_proactive_insight(city_info: dict, current: dict,
                                     historical: dict, comparison: dict,
                                     profile: dict = None) -> str:
    """Generate a brief proactive insight about current conditions, tailored to user profile."""
    context = build_rag_context(city_info, current=current)

    is_day = current.get("is_day", True)
    time_context = "daytime" if is_day else "nighttime/evening"

    profile_text = ""
    if profile:
        profile_text = (
            f"\n\nUSER PROFILE:\n"
            f"- Residence: {profile.get('residence_type', 'Unknown')}\n"
            f"- Commute: {profile.get('commute_type', 'Unknown')}\n"
            f"- Health Factors: {profile.get('health_issues', 'None')}\n"
            "Tailor your practical advice heavily to these profile factors. For example, if they use public transit, warn of wait times in cold/rain; if they live in an individual house, mention property prep for storms/snow; if they have asthma/allergies or other health factors, emphasize how the current weather might affect them."
        )

    prompt = (
        f"It is currently {time_context}. Based on the weather data below, generate a single concise insight (2-4 sentences) "
        "with practical suggestions. "
        "Do NOT mention historical averages, z-scores, percentiles, or comparisons to past data. "
        f"{'Focus on: what to wear, sunscreen needs, and daytime activities.' if is_day else 'Focus on: what to wear for the night, safety tips for low visibility, and nighttime activities.'} "
        "Be specific about the weather — mention temperature, wind, rain chances. "
        "Use a friendly, helpful tone. Do not use markdown formatting."
        f"{profile_text}\n\n" + context
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


async def generate_reminder_advisory(description: str, weather_data: dict, city_name: str) -> str:
    """Generate a specific advisory (Proceed vs Postpone) for a reminder based on weather."""
    context = ""
    if weather_data:
        context = (
            f"Location: {city_name}\n"
            f"Conditions: {weather_data.get('condition', 'Unknown')}\n"
            f"Temperature: {weather_data.get('temperature', '?')}°C\n"
            f"Wind: {weather_data.get('wind_speed', '?')} km/h\n"
            f"Precipitation: {weather_data.get('precipitation', 0)} mm\n"
        )

    prompt = (
        f"The user has a scheduled task: '{description}' in {city_name}.\n"
        f"Current weather context:\n{context}\n\n"
        "Based on this, provide a concise advisory (2-3 sentences). "
        "Explicitly recommend if they should 'Proceed' with the task or 'Postpone' it due to the weather. "
        "Be specific about why (e.g., 'The high winds might make this activity difficult'). "
        "Do not use markdown formatting. Be direct and helpful."
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "WeatherTwin is currently unable to generate a specific advisory, but please check the latest conditions before proceeding."
