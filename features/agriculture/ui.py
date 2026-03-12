"""
Agriculture — Streamlit UI component.
"""

import streamlit as st
from agent.tools import fetch_weather
from .service import get_agriculture_report


def render_agriculture_tab(city: str):
    """Render the Agricultural Weather Intelligence tab."""
    st.subheader("🌾 Agricultural Weather Intelligence")
    st.caption(f"Farming & planting insights for **{city}**")

    crop = st.text_input("Crop type (optional)", placeholder="e.g., tomato, corn, wheat", key="ag_crop")

    with st.spinner("Computing agricultural indices..."):
        weather_data = fetch_weather(city)
        if "error" in weather_data:
            st.error(f"Could not fetch weather data: {weather_data['error']}")
            return
        report = get_agriculture_report(city, weather_data, crop)

    # Metric cards
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.metric("🌡️ Growing Degree Days", f"{report.gdd}")
            st.caption("Accumulated heat units")
    with c2:
        with st.container(border=True):
            st.metric("❄️ Frost Risk", f"{report.frost_risk_pct}%")
            cls = "delta-good" if report.frost_risk_pct < 20 else ("delta-warn" if report.frost_risk_pct < 60 else "delta-bad")
            lbl = "Low" if report.frost_risk_pct < 20 else ("Moderate" if report.frost_risk_pct < 60 else "High")
            st.markdown(f'<span class="delta-chip {cls}">{lbl}</span>', unsafe_allow_html=True)
    with c3:
        with st.container(border=True):
            st.metric("💧 Soil Moisture", report.soil_moisture_est)
            moisture_cls = {"Dry": "delta-bad", "Normal": "delta-good", "Moist": "delta-warn", "Wet": "delta-warn"}
            st.markdown(f'<span class="delta-chip {moisture_cls.get(report.soil_moisture_est, "delta-warn")}">{report.soil_moisture_est}</span>', unsafe_allow_html=True)

    if report.planting_window:
        st.divider()
        with st.container(border=True):
            st.markdown(f"**📅 Recommended Planting Window:** {report.planting_window}")

    st.divider()
    with st.container(border=True):
        st.markdown("**🧑‍🌾 Expert Advice**")
        st.write(report.advice)
