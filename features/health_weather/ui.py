"""
Health Weather — Streamlit UI component.
"""

import streamlit as st
from agent.tools import fetch_weather
from .service import get_health_report


def render_health_weather_tab(city: str):
    """Render the Health & Wellness Weather Index tab."""
    st.subheader("🏥 Health & Wellness Weather Index")
    st.caption(f"Personalized health-weather analysis for **{city}**")

    condition = st.text_input(
        "Health condition (optional)",
        placeholder="e.g., asthma, allergy, migraine, arthritis",
        key="health_condition",
    )

    with st.spinner("Computing health indices..."):
        weather_data = fetch_weather(city)
        if "error" in weather_data:
            st.error(f"Could not fetch weather data: {weather_data['error']}")
            return
        report = get_health_report(city, weather_data, condition)

    idx = report.indices
    index_data = [
        ("🌿 Allergy", idx.allergy_index, "Pollen + humidity + wind"),
        ("🫁 Asthma Risk", idx.asthma_risk, "AQI + temp swings + humidity"),
        ("🧠 Migraine Trigger", idx.migraine_trigger, "Pressure changes + humidity"),
        ("🌡️ Heat Stress", idx.heat_stress, "Heat index + UV + humidity"),
        ("❄️ Cold Exposure", idx.cold_exposure, "Wind chill + precipitation"),
        ("🦴 Joint Pain", idx.joint_pain, "Pressure drops + humidity shifts"),
        ("😴 Sleep Quality", idx.sleep_quality, "Night temp + humidity (10=best)"),
    ]

    cols = st.columns(4)
    for i, (name, val, desc) in enumerate(index_data):
        with cols[i % 4]:
            with st.container(border=True):
                st.metric(name, f"{val}/10")
                # Color-coded badge
                if "Sleep" in name:
                    cls = "delta-good" if val >= 7 else ("delta-warn" if val >= 4 else "delta-bad")
                    lbl = "Good" if val >= 7 else ("Fair" if val >= 4 else "Poor")
                else:
                    cls = "delta-good" if val <= 3 else ("delta-warn" if val <= 6 else "delta-bad")
                    lbl = "Low" if val <= 3 else ("Moderate" if val <= 6 else "High")
                st.markdown(f'<span class="delta-chip {cls}">{lbl}</span>', unsafe_allow_html=True)
                st.caption(desc)

    st.divider()
    with st.container(border=True):
        st.markdown("**💡 Personalized Recommendation**")
        st.write(report.recommendation)
