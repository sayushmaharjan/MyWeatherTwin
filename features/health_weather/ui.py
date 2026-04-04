"""
Health Weather — Streamlit UI component.
"""

import streamlit as st
import asyncio
from agent.tools import fetch_weather
from .service import (
    get_health_report, fetch_openmeteo_health_data, fetch_air_quality,
    compute_sad_index, check_medication_alerts, compute_aq_composite,
    score_exercise_windows, compute_hydration, MEDICATION_RULES,
)

def get_temp_unit():
    return st.session_state.get("temp_unit", "Celsius")

def format_temp(val_c, include_unit=True):
    if val_c is None: return "--"
    pref = get_temp_unit()
    val = (val_c * 9/5) + 32 if pref == "Fahrenheit" else val_c
    unit = ("°F" if pref == "Fahrenheit" else "°C") if include_unit else ""
    return f"{round(val)}{unit}"


def run_async(coro):
    """Helper to run an async function from a synchronous context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def render_health_weather_tab(city: str):
    """Render the Health & Wellness Weather Index tab."""
    st.markdown(f"## 🏥 Health & Wellness Dashboard: {city}")
    st.markdown("""
    <style>
    .health-card {
        padding: 1.5rem;
        border-radius: 1rem;
        background: var(--highlight);
        border: 1px solid var(--border-color);
        margin-bottom: 1rem;
        transition: transform 0.2s;
        color: var(--text-primary) !important;
    }
    .health-card:hover {
        transform: translateY(-2px);
        background: rgba(255, 255, 255, 0.08);
    }
    .status-badge {
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        font-size: 0.8rem;
        font-weight: 600;
        float: right;
    }
    .badge-low { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
    .badge-mod { background: rgba(234, 179, 8, 0.2); color: #facc15; }
    .badge-high { background: rgba(239, 68, 68, 0.2); color: #f87171; }
    .badge-optimal { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
    </style>
    """, unsafe_allow_html=True)

    # Internal Tabs (Personal Tools removed)
    tab_forecast, tab_insights = st.tabs([
        "🌡️ Wellness Forecast", 
        "🧠 Deep Insights"
    ])

    # 1. Fetch data
    with st.spinner("Analyzing your environment..."):
        weather_data = fetch_weather(city)
        if "error" in weather_data:
            st.error(f"Could not fetch weather data: {weather_data['error']}")
            return
        
        # Get coordinates for Open-Meteo calls
        loc = weather_data.get("location", {})
        lat, lon = loc.get("lat"), loc.get("lon")
        
        health_data = fetch_openmeteo_health_data(lat, lon) if lat and lon else {"error": "No coords"}
        aq_data = fetch_air_quality(lat, lon) if lat and lon else {"error": "No coords"}

    # ────── TAB 1: WELLNESS FORECAST ──────
    with tab_forecast:
        user_profile = st.session_state.get("user_profile", {})
        health_condition = user_profile.get("health_issues", "General wellness")
        
        with st.spinner("Generating personalized advice..."):
            try:
                unit_p = st.session_state.get("temp_unit", "Celsius")
                report = run_async(get_health_report(city, weather_data, health_condition, unit_p))
                idx = report.indices
                recommendation = report.recommendation
            except Exception as e:
                from .service import compute_health_indices
                idx = compute_health_indices(weather_data)
                recommendation = "Could not generate personalized recommendation at this time."
        
        st.markdown(f"""
        <div style="background: rgba(59, 130, 246, 0.1); padding: 1.5rem; border-radius: 0.8rem; border-left: 5px solid #3b82f6; color: var(--text-primary); margin-bottom: 2rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <div style="font-weight: bold; color: #60a5fa;">💡 Personalized Guidance</div>
                <div style="font-size: 0.75rem; color: var(--text-secondary);">Optimized for: {health_condition}</div>
            </div>
            {recommendation}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### Daily Health Risk Analysis")
        st.caption("How today's weather patterns impact specific health conditions.")

        index_data = [
            ("🌿 Allergy", idx.allergy_index, "Pollen, humidity, and wind speeds."),
            ("🫁 Asthma Risk", idx.asthma_risk, "Air quality and rapid temperature shifts."),
            ("🧠 Migraine", idx.migraine_trigger, "Barometric pressure swings and humidity."),
            ("🌡️ Heat Stress", idx.heat_stress, "Combined effect of heat, UV, and humidity."),
            ("❄️ Cold Risk", idx.cold_exposure, "Wind chill and freezing precipitation."),
            ("🦴 Joint Pain", idx.joint_pain, "Pressure drops and humidity shifts."),
            ("😴 Sleep Quality", idx.sleep_quality, "Night-time temperature and humidity comfort."),
        ]

        cols = st.columns(2)
        for i, (name, val, desc) in enumerate(index_data):
            with cols[i % 2]:
                is_sleep = "Sleep" in name
                if is_sleep:
                    status = "Optimal" if val >= 7 else ("Fair" if val >= 4 else "Poor")
                    badge_cls = "badge-optimal" if val >= 7 else ("badge-mod" if val >= 4 else "badge-high")
                else:
                    status = "Low" if val <= 3 else ("Moderate" if val <= 6 else "High")
                    badge_cls = "badge-low" if val <= 3 else ("badge-mod" if val <= 6 else "badge-high")
                
                with st.container():
                    st.markdown(f"""
                    <div class="health-card">
                        <span class="status-badge {badge_cls}">{status}</span>
                        <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-primary);">{name}</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.8rem;">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.progress(val / 10.0)
                    st.write("") 

    # ────── TAB 2: DEEP INSIGHTS ──────
    with tab_insights:
        st.markdown("### 🧠 Seasonal Affective Disorder (SAD) Index")
        if "error" not in health_data:
            sad = compute_sad_index(health_data.get("daily", {}))
            s_col1, s_col2 = st.columns([1, 2])
            with s_col1:
                sad_color = "#f87171" if sad.risk_level == "High" else ("#facc15" if sad.risk_level == "Moderate" else "#4ade80")
                st.markdown(f"""
                <div style="text-align: center; padding: 1.5rem; border: 2px solid {sad_color}; border-radius: 1rem; color: var(--text-primary);">
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">RISK SCORE</div>
                    <div style="font-size: 2.2rem; font-weight: bold; color: {sad_color};">{sad.sad_index}/100</div>
                    <div style="font-weight: 600;">{sad.risk_level} Risk</div>
                </div>
                """, unsafe_allow_html=True)
            with s_col2:
                st.markdown(f"**Analysis Summary:**")
                st.write(f"• Avg sunshine: {sad.avg_sunshine_hrs_14d} hrs/day (last 14 days)")
                st.write(f"• Low-sun days: {sad.consecutive_low_sun_days}/14 days (< 1hr sun)")
                st.info(f"💡 {sad.recommendation}")
        
        st.divider()
        st.markdown("### 🌬️ Environment & Activity Guide")
        if "error" not in aq_data:
            aq = compute_aq_composite(aq_data)
            aq_c1, aq_c2 = st.columns([1, 2])
            with aq_c1:
                st.metric("US EPA AQI", aq.us_aqi, help="Standard EPA index for air quality.")
                st.caption(f"Worst Pollutant: {aq.worst_pollutant}")
            with aq_c2:
                st.markdown(f"**{aq.icon} {aq.tier}**")
                for act in aq.activity_guidance:
                    st.write(f"• {act}")
        
        st.divider()
        st.markdown("### 🏃 Top Outdoor Exercise Windows")
        if "error" not in health_data:
            windows = score_exercise_windows(health_data.get("hourly", {}))
            if windows:
                ex_cols = st.columns(3)
                medals = ["🥇", "🥈", "🥉"]
                for i, w in enumerate(windows[:3]):
                    with ex_cols[i]:
                        st.markdown(f"**{medals[i]} {w.time_label}**")
                        st.markdown(f"""
                        <div style="background: var(--highlight); padding: 1rem; border-radius: 0.5rem; text-align: center; color: var(--text-primary);">
                            <div style="font-size: 1.2rem; font-weight: bold;">{w.score}%</div>
                            <div style="font-size: 0.7rem; color: var(--text-secondary);">OPTIMAL</div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption(f"🌡️ {format_temp(w.temp_c)} · ☀️ UV {w.uv_index}")
