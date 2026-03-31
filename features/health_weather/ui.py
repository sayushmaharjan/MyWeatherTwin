"""
Health Weather — Streamlit UI component.
"""

import streamlit as st
from agent.tools import fetch_weather
from .service import (
    get_health_report, fetch_openmeteo_health_data, fetch_air_quality,
    compute_sad_index, check_medication_alerts, compute_aq_composite,
    score_exercise_windows, compute_hydration, MEDICATION_RULES,
)


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

    # ═══════════════════════════════════════════════════
    #  NEW SECTIONS: Advanced Health Features
    # ═══════════════════════════════════════════════════

    # Get coordinates for Open-Meteo calls
    loc = weather_data.get("location", {})
    lat = loc.get("lat")
    lon = loc.get("lon")

    if not lat or not lon:
        st.caption("ℹ️ Advanced health features require location coordinates.")
        return

    # Fetch Open-Meteo health data (shared by SAD + Exercise)
    with st.spinner("Loading advanced health data..."):
        health_data = fetch_openmeteo_health_data(lat, lon)
        aq_data = fetch_air_quality(lat, lon)

    # ── 1. SAD Index ──────────────────────────────────
    st.divider()
    st.subheader("🧠 SAD Index (Seasonal Affective Disorder)")

    if "error" not in health_data:
        sad = compute_sad_index(health_data.get("daily", {}))

        col1, col2 = st.columns([1, 2])
        with col1:
            with st.container(border=True):
                color = "🔴" if sad.risk_level == "High" else "🟡" if sad.risk_level == "Moderate" else "🟢"
                st.metric(f"{color} SAD Index", f"{sad.sad_index}/100",
                          help="0=No risk, 100=High risk")
                cls = "delta-bad" if sad.risk_level == "High" else "delta-warn" if sad.risk_level == "Moderate" else "delta-good"
                st.markdown(f'<span class="delta-chip {cls}">{sad.risk_level}</span>', unsafe_allow_html=True)
                st.caption(f"Avg sunshine last 14 days: {sad.avg_sunshine_hrs_14d} hrs/day")
                st.caption(f"Low-sun days (< 1hr): {sad.consecutive_low_sun_days}/14")
        with col2:
            with st.container(border=True):
                st.info(f"💡 {sad.recommendation}")
    else:
        st.warning("Could not fetch sunshine data for SAD analysis.")

    # ── 2. Medication Storage Alerts ──────────────────
    st.divider()
    st.subheader("💊 Medication Storage Monitor")

    user_meds = st.multiselect(
        "Select your medications",
        options=list(MEDICATION_RULES.keys()),
        format_func=lambda x: x.replace("_", " ").title(),
        key="health_meds_select",
    )

    if user_meds:
        alerts = check_medication_alerts(weather_data, user_meds)

        if not alerts:
            st.success("✅ Current conditions are safe for all your medications.")
        for alert in alerts:
            severity_icon = "🚨" if alert.severity == "HIGH" else "⚠️"
            with st.expander(f"{severity_icon} {alert.medication.replace('_', ' ').title()} Alert"):
                for issue in alert.issues:
                    st.write(f"• {issue}")
                st.caption(alert.note)
    else:
        st.caption("Select medications above to monitor storage conditions.")

    # ── 3. Air Quality Composite ──────────────────────
    st.divider()
    st.subheader("🌬️ Air Quality & Activity Guide")

    if "error" not in aq_data:
        aq = compute_aq_composite(aq_data)

        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True):
                st.metric(f"{aq.icon} US AQI", aq.us_aqi if aq.us_aqi else "N/A")
                st.caption("EPA standard index")
        with col2:
            with st.container(border=True):
                st.metric("PM2.5", f"{aq.pm2_5} µg/m³" if aq.pm2_5 else "N/A")
                st.caption("Fine particulate matter")
        with col3:
            with st.container(border=True):
                st.metric("Worst Pollutant", aq.worst_pollutant)
                st.caption("Primary concern")

        with st.container(border=True):
            st.markdown(f"**{aq.icon} {aq.tier}**")
            for act in aq.activity_guidance:
                st.write(f"• {act}")
    else:
        st.warning("Air quality data unavailable for this location.")

    # ── 4. Outdoor Exercise Windows ───────────────────
    st.divider()
    st.subheader("🏃 Best Outdoor Exercise Windows")

    if "error" not in health_data:
        hourly = health_data.get("hourly", {})
        windows = score_exercise_windows(hourly)

        if windows:
            medals = ["🥇", "🥈", "🥉"]
            ex_cols = st.columns(3)
            for i, w in enumerate(windows[:3]):
                with ex_cols[i]:
                    with st.container(border=True):
                        st.markdown(f"### {medals[i]} {w.time_label}")
                        st.metric("Score", f"{w.score}/100")
                        st.caption(f"🌡️ {w.temp_c}°C · ☀️ UV {w.uv_index} · 🌧️ {w.precip_prob}% rain")
        else:
            st.info("No exercise window data available for today.")
    else:
        st.warning("Could not compute exercise windows.")

    # ── 5. Hydration Estimator ────────────────────────
    st.divider()
    st.subheader("💧 Hydration Estimator")

    cur = weather_data.get("current", {})
    temp_c = cur.get("temp_c", 20)
    humidity = cur.get("humidity", 50)

    h_col1, h_col2 = st.columns(2)
    with h_col1:
        weight = st.number_input("Your weight (kg)", min_value=30.0, max_value=200.0,
                                 value=70.0, step=5.0, key="hydration_weight")
    with h_col2:
        activity = st.selectbox("Activity level", [
            "sedentary", "light_walk", "moderate_exercise", "intense_exercise",
        ], format_func=lambda x: x.replace("_", " ").title(), key="hydration_activity")

    hydration = compute_hydration(temp_c, humidity, activity, weight)

    hyd_col1, hyd_col2, hyd_col3 = st.columns(3)
    with hyd_col1:
        with st.container(border=True):
            st.metric("💧 Daily Need", f"{hydration.total_ml} ml")
    with hyd_col2:
        with st.container(border=True):
            st.metric("🥤 Cups (8 oz)", hydration.cups_8oz)
    with hyd_col3:
        with st.container(border=True):
            st.metric("🌡️ Current Temp", f"{temp_c}°C")
            st.caption(f"Humidity: {humidity}%")

    st.info(f"💡 **Tip:** {hydration.tip}")
