"""
Agriculture — Streamlit UI component.
"""

import streamlit as st
import pandas as pd
from agent.tools import fetch_weather
from .service import (
    get_agriculture_report, fetch_agriculture_data,
    compute_irrigation_schedule, compute_livestock_heat_stress,
    compute_disease_risk, compute_field_work_windows,
    compute_harvest_quality,
    CROP_KC, SPECIES_THRESHOLDS, HARVEST_QUALITY_RULES, DRY_DAYS_NEEDED,
)


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

    # ═══════════════════════════════════════════════════
    #  NEW SECTIONS: Advanced Agriculture Features
    # ═══════════════════════════════════════════════════

    loc = weather_data.get("location", {})
    lat = loc.get("lat")
    lon = loc.get("lon")

    if not lat or not lon:
        st.caption("ℹ️ Advanced agriculture features require location coordinates.")
        return

    with st.spinner("Loading advanced agriculture data from Open-Meteo..."):
        ag_data = fetch_agriculture_data(lat, lon)

    if "error" in ag_data:
        st.warning(f"Could not fetch agriculture data: {ag_data['error']}")
        return

    # ── 1. Irrigation Scheduler ───────────────────────
    st.divider()
    st.subheader("💧 Irrigation Scheduler")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        irr_crop = st.selectbox("Crop", list(CROP_KC.keys()), key="irr_crop")
    with col2:
        stage = st.selectbox("Growth Stage", ["initial", "mid", "late"], key="irr_stage", index=1)
    with col3:
        soil = st.selectbox("Soil Type", ["sandy", "sandy_loam", "loam", "clay_loam", "clay"],
                            key="irr_soil", index=2)
    with col4:
        area = st.number_input("Area (hectares)", min_value=0.1, value=1.0, step=0.5, key="irr_area")

    irr = compute_irrigation_schedule(ag_data, irr_crop, stage, soil, area)

    if irr.next_irrigation:
        nxt = irr.next_irrigation
        st.warning(f"🚿 Next irrigation: **{nxt.date}** — {nxt.deficit_mm}mm deficit "
                   f"({nxt.water_needed_liters:,} liters)")
    else:
        st.success("✅ No irrigation needed this week — soil moisture is adequate.")

    if irr.schedule:
        df = pd.DataFrame([d.model_dump() for d in irr.schedule])
        df["irrigate_today"] = df["irrigate_today"].map({True: "🚿 Yes", False: "✅ No"})
        display_cols = ["date", "crop_water_need_mm", "effective_rain_mm",
                        "soil_moisture_pct", "irrigate_today", "water_needed_liters"]
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available_cols], use_container_width=True, hide_index=True)

    # ── 2. Livestock Heat Stress Monitor ──────────────
    st.divider()
    st.subheader("🐄 Livestock Heat Stress Monitor")

    species = st.selectbox("Livestock Type",
        list(SPECIES_THRESHOLDS.keys()),
        format_func=lambda x: x.replace("_", " ").title(),
        key="livestock_species")

    thi_result = compute_livestock_heat_stress(ag_data, species)

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("Current THI", thi_result.current_thi, help="<68 safe for dairy cattle")
    with col2:
        with st.container(border=True):
            st.metric("Status", thi_result.current_level)
    with col3:
        with st.container(border=True):
            peak_time_short = thi_result.peak_time[11:16] if len(thi_result.peak_time) > 11 else thi_result.peak_time
            st.metric("Peak THI (24hr)", thi_result.peak_thi, f"at {peak_time_short}")

    if thi_result.danger_hours_count > 0:
        st.error(f"⚠️ {thi_result.danger_hours_count} danger-level hours forecast in next 24hrs")

    if thi_result.mitigations:
        with st.container(border=True):
            st.markdown("**Recommended Actions**")
            for action in thi_result.mitigations:
                st.write(f"• {action}")

    # ── 3. Crop Disease Calendar ──────────────────────
    st.divider()
    st.subheader("🦠 Crop Disease Calendar")

    user_crops = st.multiselect("Your crops",
        ["corn", "wheat", "soybeans", "tomatoes", "potatoes", "grapes", "vegetables"],
        key="disease_crops")

    if user_crops:
        diseases = compute_disease_risk(ag_data, user_crops)

        if not diseases:
            st.success("✅ No disease risk detected in the next 72 hours for your crops.")

        for alert in diseases:
            severity_color = "🔴" if alert.severity == "HIGH" else "🟡"
            with st.expander(f"{severity_color} {alert.disease} — Risk: {alert.risk_percent}%"):
                st.write(f"**Pathogen:** {alert.pathogen}")
                st.write(f"**Affects:** {', '.join(alert.affected_crops)}")
                st.write(f"**Favorable conditions start in:** ~{alert.window_starts_in_hrs} hours")
                st.warning(f"**Action:** {alert.action}")
    else:
        st.caption("Select your crops above to monitor disease risk.")

    # ── 4. Field Work Windows ─────────────────────────
    st.divider()
    st.subheader("🚜 Field Work Windows")

    fw_col1, fw_col2 = st.columns(2)
    with fw_col1:
        operation = st.selectbox("Operation Type",
            list(DRY_DAYS_NEEDED.keys()),
            format_func=lambda x: x.replace("_", " ").title(),
            key="fw_operation")
    with fw_col2:
        fw_soil = st.selectbox("Soil Type", ["sandy", "loam", "clay"], key="fw_soil", index=1)

    field_windows = compute_field_work_windows(ag_data, fw_soil, operation)
    next_workable = next((w for w in field_windows if w.trafficable), None)

    if next_workable:
        st.success(f"✅ Next workable day: **{next_workable.date}**")
    else:
        st.error("🚫 No workable days in the next 7 days — too wet or conditions unfavorable")

    for w in field_windows:
        icon = "✅" if w.trafficable else ("❄️" if w.frozen else "🚫")
        risk_color = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
        st.write(f"{icon} **{w.date}** — Rain: {w.rain_mm}mm | "
                 f"Compaction Risk: {risk_color.get(w.compaction_risk, '❓')} {w.compaction_risk} | "
                 f"Forecast confidence: {w.confidence}")

    # ── 5. Harvest Quality Predictor ──────────────────
    st.divider()
    st.subheader("🌾 Harvest Quality Predictor")

    h_crop = st.selectbox("Crop to Harvest", list(HARVEST_QUALITY_RULES.keys()), key="harvest_crop")

    harvest = compute_harvest_quality(ag_data, h_crop)

    if harvest.best_harvest_day:
        best = harvest.best_harvest_day
        st.success(f"🏆 Best harvest window: **{best.date}** — Score {best.quality_score}/100 ({best.grade})")
        st.caption(f"Target grain moisture: {harvest.moisture_target_pct}% | Rain sensitivity: {harvest.rain_sensitivity}")

    for w in harvest.windows:
        icon = "✅" if w.harvest_recommended else "❌"
        with st.expander(f"{icon} {w.date} — Score: {w.quality_score}/100 | {w.grade}"):
            st.write(f"Rain: {w.rain_mm}mm | Avg Humidity: {w.avg_humidity_pct}%")
            for risk in w.risks:
                st.warning(risk)
            if not w.risks:
                st.success("No quality risks detected")
