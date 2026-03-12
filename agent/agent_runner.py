"""
Agent runner — initializes the LLM, registers tools, runs the agent workflow.
"""

import json
import streamlit as st
from datetime import datetime

from config import client, MODEL, LOG_FILE
from .tool_schemas import SYSTEM_PROMPT, parse_agent_response
from .tools import get_weather

# ── Feature tool imports ───────────────────────────────
from features.extreme_weather.tools import extreme_weather_tool
from features.health_weather.tools import health_weather_tool
from features.agriculture.tools import agriculture_tool
from features.travel_planner.tools import travel_planner_tool
from features.climate_news.tools import climate_news_tool
from features.smart_recommender.tools import smart_recommender_tool
from features.climate_simulator.tools import climate_simulator_tool


# ── Tool Registry ──────────────────────────────────────
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "extreme_weather": extreme_weather_tool,
    "health_weather": health_weather_tool,
    "agriculture": agriculture_tool,
    "travel_planner": travel_planner_tool,
    "climate_news": climate_news_tool,
    "smart_recommender": smart_recommender_tool,
    "climate_simulator": climate_simulator_tool,
}


# ── Event Logging ──────────────────────────────────────

def log_query(user_input: str, bot_response: str, weather_data: str = None, source: str = "API"):
    """Append a query event to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"Timestamp   : {timestamp}\n")
        f.write(f"Source      : {source}\n")
        f.write(f"User Query  : {user_input}\n")
        if weather_data:
            f.write(f"Weather Data: {weather_data}\n")
        f.write(f"Bot Response: {bot_response}\n")
        f.write("=" * 60 + "\n\n")


# ── Agent Loop ─────────────────────────────────────────

def run_agent(user_input: str) -> str:
    """Run the ReAct-style agent loop: think → act → observe → answer."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    max_steps = 5
    step = 0
    weather_info = None

    while step < max_steps:
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0,
            )
        except Exception as e:
            error_msg = f"❌ API Error: {str(e)}"
            log_query(user_input, error_msg)
            return error_msg

        content = response.choices[0].message.content.strip()

        try:
            content_json = parse_agent_response(content)
            action = content_json.get("action", "")
            action_input = content_json.get("action_input", "")

            if action == "user_answer":
                log_query(user_input, action_input, weather_info, source="API")
                return action_input

            # Dispatch to registered tools
            if action in TOOL_REGISTRY:
                tool_fn = TOOL_REGISTRY[action]
                observation = tool_fn(action_input)
                if action == "get_weather":
                    weather_info = observation
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"Observation: {observation}\n\nNow respond with a user_answer action containing the full response for the user.",
                })
            else:
                error_msg = f"Unknown action: {action}"
                log_query(user_input, error_msg)
                return error_msg

        except json.JSONDecodeError:
            log_query(user_input, content, weather_info, source="API")
            return content

        step += 1

    error_msg = "⚠️ Max steps reached."
    log_query(user_input, error_msg)
    return error_msg


# ── AI Overview ────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def get_ai_overview(_weather_json: str) -> str:
    """Generate a natural-language weather overview using the LLM."""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a weather forecaster that responds in natural language."},
                {
                    "role": "user",
                    "content": (
                        "How should one prepare for the weather today? What should they wear, "
                        "pack, or keep in mind? The JSON data for the local weather forecast is "
                        "below. Talk as if you're on air for one person. 350 characters maximum. "
                        f"{_weather_json}"
                    ),
                },
            ],
            model=MODEL,
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Unable to generate overview: {e}"
