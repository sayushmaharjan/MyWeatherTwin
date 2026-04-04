"""
Smart Recommender — core business logic.
Generates structured daily predictions via LLM based on weather, health, and commute profiles.
"""

import json
from config import client, MODEL
from .models import Recommendations


async def get_smart_recommendations(
    city: str, 
    weather_data: dict, 
    user_profile: dict = None,
    unit_pref: str = "Celsius"
) -> Recommendations:
    """
    Generate highly structured daily predictions.
    
    Acts as a Senior Software Engineer and LLM Expert persona to synthesize 
    weather, health, and commute data.
    """
    cur = weather_data.get("current", {})
    # Fixed field names based on the RAG context logic in backend/llm_service.py
    condition = cur.get("condition", "Normal")
    temp_c = cur.get("temperature", 20)
    humidity = cur.get("humidity", 50)
    wind_kph = cur.get("wind_speed", 10)
    uv = cur.get("uv_index", 3)
    precip = cur.get("precipitation", 0)

    u = "°F" if unit_pref == "Fahrenheit" else "°C"
    # Basic conversion
    val_temp = temp_c
    if unit_pref == "Fahrenheit":
        val_temp = (temp_c * 9/5) + 32

    weather_summary = (
        f"Location: {city}. Current Weather: {condition}, {val_temp:.1f}{u}. "
        f"Humidity: {humidity}%, Wind: {wind_kph} km/h, UV: {uv}, Precip: {precip}mm."
    )

    # Extract relevant profile details
    health_context = "No specific health conditions reported."
    commute_context = "Commute details not provided."
    
    if user_profile:
        health_context = user_profile.get("health_issues", health_context) or health_context
        commute_context = f"Mode: {user_profile.get('commute_type', 'Unknown')}"

    system_prompt = (
        "You are a senior software engineer and an LLM expert. "
        "Your task is to generate a concise, user-friendly daily prediction. "
        "Combine weather severity, health sensitivity, and commute impact. "
        "\n\nRules:\n"
        "1. Keep language simple and non-technical.\n"
        "2. Be concise and avoid long paragraphs.\n"
        "3. Prioritize personalization over generic weather reporting.\n"
        "4. Do NOT repeat raw weather data; interpret it.\n"
        "5. Identify 3-4 EXACT landmarks, venues, or specific businesses in/near the city that are great to visit in this weather. "
        "DO NOT use generic categories like 'Museums' or 'Parks'. Use REAL names (e.g., 'The Nelson-Atkins Museum of Art' instead of 'Art Gallery').\n"
        "6. Output MUST be valid JSON matching this schema:\n"
        "{\n"
        "  \"smart_summary\": \"string (2-3 lines max)\",\n"
        "  \"health_alerts\": [\"string (max 3 bullets)\"],\n"
        "  \"commute_insights\": [\"string (2-3 bullets)\"],\n"
        "  \"risk_score\": \"Low / Moderate / High\",\n"
        "  \"recommendations\": [\"string (3-5 bullets)\"],\n"
        "  \"suggested_places\": [\"string (3-4 EXACT local names with their common emoji)\"]\n"
        "}\n\n"
        f"IMPORTANT: The user prefers {unit_pref}. Please interpret weather and provide all insights using {unit_pref} logic and symbols."
    )

    user_input = (
        f"Location: {city}\n"
        f"Weather Data: {weather_summary}\n"
        f"User Health Conditions: {health_context}\n"
        f"User Commute Details: {commute_context}"
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.7,
            max_tokens=700,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content.strip())
        return Recommendations(city=city, **data)
    except Exception as e:
        print(f"Error generating recommendations in service: {e}")
        # Return structured fallback data
        return Recommendations(
            city=city,
            smart_summary=f"Plan for a {str(condition).lower()} day in {city}.",
            health_alerts=["Standard weather precautions apply."],
            commute_insights=["No major weather-related travel disruptions expected."],
            risk_score="Low",
            recommendations=["Check your local forecast for updates.", "Have a great day!"],
            suggested_places=["Local Libraries" if temp_c < 15 else "The City Center Park"]
        )
