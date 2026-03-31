"""
Travel Planner — Streamlit UI component.
Enhanced with calendar dates, travel mode, health packing, itinerary, weather diff, and route map.
Also includes: Road Condition Predictor, Best Travel Window, Flight Delay Risk.
"""

import streamlit as st
import datetime
import pandas as pd
import requests as sync_requests
from .service import (
    get_travel_report, fetch_road_weather, compute_road_conditions,
    compute_travel_window, compute_flight_delay,
)


# ── Airport Lookup ────────────────────────────────
AIRPORT_LOOKUP = {
    "Chicago O'Hare": "KORD", "JFK New York": "KJFK",
    "LAX Los Angeles": "KLAX", "Dallas/Fort Worth": "KDFW",
    "Atlanta Hartsfield": "KATL", "Denver": "KDEN",
    "San Francisco": "KSFO", "Miami": "KMIA",
    "Seattle": "KSEA", "Boston Logan": "KBOS",
    "Las Vegas": "KLAS", "Phoenix": "KPHX",
    "Minneapolis": "KMSP", "Detroit": "KDTW",
    "Orlando": "KMCO", "Houston": "KIAH",
    "Other (enter ICAO code)": "custom",
}


def render_travel_planner_tab(city: str):
    """Render the enhanced Travel Weather Planner tab."""

    st.markdown("""
    <div style="margin-bottom:10px;">
        <div style="font-size:1.4rem; font-weight:800; background:linear-gradient(135deg,#3b82f6,#8b5cf6);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">✈️ Travel Weather Planner</div>
        <div style="font-size:0.72rem; color:#94a3b8; margin-top:2px;">Plan your trip with weather intelligence, personalized packing & itinerary</div>
    </div>
    """, unsafe_allow_html=True)

    # ─── User context from profile ─────────────
    profile = st.session_state.get("user_profile", {}) or {}
    home_city = profile.get("home_address", "") or ""
    health_issues = profile.get("health_issues", "") or ""

    # ─── Inputs — compact 4-column row ────────
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    with c1:
        destination = st.text_input("🏙️ Destination", value=city or "", placeholder="e.g. Tokyo, Paris...", key="travel_dest_v4")
    with c2:
        travel_mode = st.radio("🚀 Mode", ["✈️ Flight", "🚗 Car"], horizontal=True, key="travel_mode_v4")
    with c3:
        start_date = st.date_input("📅 Start", value=tomorrow, min_value=datetime.date.today(), key="travel_start_v4")
    with c4:
        end_date = st.date_input("📅 End", value=tomorrow + datetime.timedelta(days=3), min_value=tomorrow, key="travel_end_v4")

    # Context pills + button
    pill_col, btn_col = st.columns([3, 1])
    with pill_col:
        ctx_parts = []
        if home_city:
            ctx_parts.append(f"<span style='background:rgba(59,130,246,0.15);color:#60a5fa;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;'>🏠 {home_city}</span>")
        if health_issues:
            ctx_parts.append(f"<span style='background:rgba(244,63,94,0.15);color:#f43f5e;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;'>💊 {health_issues}</span>")
        if not home_city:
            ctx_parts.append("<span style='font-size:0.68rem;color:#64748b;'>⚠️ Set home address in sidebar for weather comparison</span>")
        if ctx_parts:
            st.markdown(f"<div style='display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;'>{''.join(ctx_parts)}</div>", unsafe_allow_html=True)
    with btn_col:
        generate = st.button("✈️ Get Travel Plan", key="travel_gen_btn_v4", use_container_width=True)

    # ─── Generate ──────────────────────────────
    if generate:
        if not destination:
            st.error("Please enter a destination city.")
            return
        if end_date < start_date:
            st.error("End date must be after start date.")
            return

        num_days = (end_date - start_date).days + 1
        mode_clean = "Car" if "Car" in travel_mode else "Flight"

        with st.spinner("🌍 Generating your personalized travel plan..."):
            report = get_travel_report(
                destination=destination,
                month=start_date.strftime("%B"),
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                num_days=num_days,
                home_city=home_city,
                health_issues=health_issues,
                travel_mode=mode_clean,
            )
        st.session_state["travel_report_v4"] = report

    # ─── Display results ───────────────────────
    report = st.session_state.get("travel_report_v4")
    if not report:
        pass  # Don't return — still render the road/flight sections below
    else:
        # Header bar
        mode_emoji = "🚗" if report.travel_mode == "Car" else "✈️"
        st.markdown(f"""
        <div style="background:linear-gradient(145deg,rgba(59,130,246,0.08),rgba(139,92,246,0.08));
                    border:1px solid rgba(59,130,246,0.2);border-radius:12px;padding:8px 14px;margin:6px 0;">
            <span style="font-size:1rem;font-weight:700;color:#f8fafc;">{mode_emoji} {report.destination}</span>
            <span style="font-size:0.7rem;color:#94a3b8;margin-left:12px;">
                📅 {report.start_date} → {report.end_date} · {report.num_days}d · {report.travel_mode}
                {f' · 🏠 {report.home_city}' if report.home_city else ''}
            </span>
        </div>
        """, unsafe_allow_html=True)

        # ─── Grid layout — 2 columns, compact cards ─
        col_l, col_r = st.columns(2)

        with col_l:
            with st.expander("🌤️ **Destination Weather**", expanded=True):
                st.markdown(report.profile)

            with st.expander("🗺️ **Day-by-Day Itinerary**", expanded=True):
                st.markdown(report.itinerary)

        with col_r:
            packing_title = "🎒 **Packing List (Health-Aware)**" if report.health_issues else "🎒 **Packing List**"
            with st.expander(packing_title, expanded=True):
                st.markdown(report.packing_list)

            with st.expander("🔄 **Weather: Home vs Destination**", expanded=True):
                st.markdown(report.weather_diff)

        # Risk — compact inline
        risk_label = "🚗 Driving Risk" if report.travel_mode == "Car" else "✈️ Flight Risk"
        st.markdown(f"""
        <div style="background:rgba(17,24,39,0.5);border:1px solid rgba(148,163,184,0.1);
                    border-radius:10px;padding:8px 14px;margin-top:4px;">
            <span style="font-size:0.7rem;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:0.5px;">{risk_label}</span>
            <span style="color:#cbd5e1;font-size:0.8rem;margin-left:8px;">{report.flight_risk}</span>
        </div>
        """, unsafe_allow_html=True)

        # Route map for car
        if report.travel_mode == "Car" and report.route_coords:
            _render_route_map(report)

    # ═══════════════════════════════════════════════════
    #  NEW SECTIONS: Road Conditions + Travel Window + Flight Delay
    # ═══════════════════════════════════════════════════

    # Get location coordinates
    wd = st.session_state.get("weather_data")
    lat, lon = None, None
    if wd:
        city_info = wd.get("city", {})
        lat = city_info.get("latitude")
        lon = city_info.get("longitude")

    # ── 1. Road Condition Predictor ───────────────────
    st.divider()
    st.markdown("""
    <div style="margin-bottom:8px;">
        <div style="font-size:1.2rem; font-weight:800; background:linear-gradient(135deg,#06b6d4,#3b82f6);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🧊 Road Condition Predictor</div>
        <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">Black ice detection, fog analysis & 24-hour road safety timeline</div>
    </div>
    """, unsafe_allow_html=True)

    if lat and lon:
        with st.spinner("Fetching road weather data..."):
            road_data = fetch_road_weather(lat, lon)
            road = compute_road_conditions(road_data)

        if road.current:
            current = road.current
            col1, col2, col3 = st.columns(3)
            with col1:
                with st.container(border=True):
                    st.metric(
                        f"{current.ice.icon} Road Surface",
                        current.ice.condition,
                        f"{current.ice.surface_temp_c}°C",
                    )
            with col2:
                with st.container(border=True):
                    vis_display = f"{current.fog.visibility_m:.0f}m" if current.fog.visibility_m < 10000 else "10+ km"
                    st.metric(
                        f"{current.fog.icon} Visibility",
                        vis_display,
                        current.fog.density,
                    )
            with col3:
                with st.container(border=True):
                    st.metric(
                        "⚠️ Stopping Distance",
                        f"{current.ice.stopping_distance_multiplier}x normal",
                        help="Multiplier vs dry road stopping distance",
                    )

            # Risk factors
            if current.ice.risk_factors:
                with st.container(border=True):
                    st.markdown("**⚠️ Active Risk Factors:**")
                    for f in current.ice.risk_factors:
                        st.write(f"  • {f}")

            st.caption(f"💡 {current.fog.speed_advice}")

            # Peak danger alert
            if road.peak_danger_score >= 40:
                st.warning(f"⚠️ Peak danger at **{road.peak_danger_time}** — Score {road.peak_danger_score}/100. "
                          f"Safe hours: {road.safe_hours_count}/24")

            # 24hr timeline
            with st.expander("📊 24-Hour Road Risk Timeline"):
                df = pd.DataFrame([{
                    "Time": r.time_label,
                    "Ice Risk": r.ice.risk_score,
                    "Visibility (m)": r.fog.visibility_m,
                    "Condition": r.ice.condition,
                    "Safe": "✅" if r.safe_to_drive else "⚠️"
                } for r in road.hourly])
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Road condition data unavailable for this location.")
    else:
        st.caption("ℹ️ Search for a city to see road conditions.")

    # ── 2. Best Travel Window ─────────────────────────
    st.divider()
    st.markdown("""
    <div style="margin-bottom:8px;">
        <div style="font-size:1.2rem; font-weight:800; background:linear-gradient(135deg,#f59e0b,#ef4444);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🗓️ Best Travel Window</div>
        <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">7-day road trip scoring — weather at origin, midpoint & destination</div>
    </div>
    """, unsafe_allow_html=True)

    tw_col1, tw_col2 = st.columns(2)
    with tw_col1:
        st.write(f"**Origin:** {'Your current location' if lat else 'Search for a city first'}")
    with tw_col2:
        dest_city_tw = st.text_input("Destination city", placeholder="e.g. Chicago, IL",
                                     key="travel_window_dest")
        trip_hrs = st.slider("Estimated drive time (hours)", 1.0, 12.0, 4.0, 0.5,
                             key="travel_window_hrs")

    if dest_city_tw and lat and lon:
        # Geocode destination
        try:
            geo = sync_requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": dest_city_tw, "count": 1},
                timeout=10,
            ).json()
        except Exception:
            geo = {}

        if geo.get("results"):
            dest = geo["results"][0]
            with st.spinner("Computing 7-day travel corridor..."):
                tw_result = compute_travel_window(
                    lat, lon, dest["latitude"], dest["longitude"], trip_hrs
                )

            if tw_result.best_travel_day:
                best = tw_result.best_travel_day
                st.success(f"🏆 Best day to travel: **{best.day}** — "
                          f"Score {best.corridor_score}/100 ({best.grade})")

            for day in tw_result.daily_scores:
                with st.expander(f"{day.grade} — {day.day} (Score: {day.corridor_score}/100)"):
                    dc1, dc2 = st.columns(2)
                    dc1.write(f"☔ Origin rain: {day.origin_precip}mm | ❄️ Snow: {day.origin_snow}cm")
                    dc2.write(f"☔ Destination rain: {day.dest_precip}mm")
                    if day.corridor_score < 70:
                        st.warning(f"Worst conditions at: **{day.worst_point}**")
        else:
            st.warning(f"Could not find '{dest_city_tw}'. Try a different city name.")

    # ── 3. Flight Delay Risk ──────────────────────────
    st.divider()
    st.markdown("""
    <div style="margin-bottom:8px;">
        <div style="font-size:1.2rem; font-weight:800; background:linear-gradient(135deg,#8b5cf6,#ec4899);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">✈️ Flight Delay Risk</div>
        <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">Real-time METAR analysis — thunderstorms, visibility, wind & de-icing queues</div>
    </div>
    """, unsafe_allow_html=True)

    fl_col1, fl_col2 = st.columns(2)
    with fl_col1:
        origin_select = st.selectbox("🛫 Departure Airport",
                                     list(AIRPORT_LOOKUP.keys()), key="flight_origin")
        if origin_select == "Other (enter ICAO code)":
            origin_icao = st.text_input("Origin ICAO code (e.g. KORD)", key="flight_origin_custom")
        else:
            origin_icao = AIRPORT_LOOKUP[origin_select]
    with fl_col2:
        dest_select = st.selectbox("🛬 Arrival Airport",
                                   list(AIRPORT_LOOKUP.keys()), key="flight_dest")
        if dest_select == "Other (enter ICAO code)":
            dest_icao = st.text_input("Destination ICAO code", key="flight_dest_custom")
        else:
            dest_icao = AIRPORT_LOOKUP[dest_select]

    if origin_icao and dest_icao and origin_icao != "custom" and dest_icao != "custom" and origin_icao != dest_icao:
        if st.button("🔍 Check Flight Delay Risk", key="check_flight_delay"):
            with st.spinner("Fetching aviation weather data..."):
                flight_result = compute_flight_delay(origin_icao, dest_icao)

            st.session_state["flight_delay_result"] = flight_result
            st.session_state["flight_labels"] = (origin_select, dest_select)

    flight_result = st.session_state.get("flight_delay_result")
    if flight_result:
        labels = st.session_state.get("flight_labels", ("Origin", "Destination"))
        fr_col1, fr_col2 = st.columns(2)

        for col, airport_data, label in [
            (fr_col1, flight_result.origin, f"🛫 {labels[0]}"),
            (fr_col2, flight_result.destination, f"🛬 {labels[1]}"),
        ]:
            with col:
                with st.container(border=True):
                    st.metric(label, airport_data.risk_level,
                              f"Score: {airport_data.delay_risk_score}/100")
                    if airport_data.visibility_sm is not None:
                        st.caption(f"Visibility: {airport_data.visibility_sm}sm | "
                                   f"Wind: {airport_data.wind_kt}kt")
                    for reason in airport_data.delay_reasons:
                        st.warning(reason)
                    if not airport_data.delay_reasons:
                        st.success("✅ No significant weather delays expected")


def _render_route_map(report):
    """Render an interactive folium route map for car travel."""
    try:
        import folium
        from streamlit_folium import st_folium

        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

        home_ll = report.home_coords
        dest_ll = report.dest_coords
        route = report.route_coords

        mid_lat = (home_ll[0] + dest_ll[0]) / 2
        mid_lon = (home_ll[1] + dest_ll[1]) / 2

        m = folium.Map(location=[mid_lat, mid_lon], zoom_start=5, tiles="cartodbdark_matter")

        folium.PolyLine(
            route, color="#3b82f6", weight=4, opacity=0.85, tooltip="Driving Route",
        ).add_to(m)

        folium.Marker(
            [home_ll[0], home_ll[1]],
            tooltip=f"🏠 {report.home_city}",
            popup=f"Start: {report.home_city}",
            icon=folium.Icon(color="green", icon="home", prefix="fa"),
        ).add_to(m)

        folium.Marker(
            [dest_ll[0], dest_ll[1]],
            tooltip=f"📍 {report.destination}",
            popup=f"Destination: {report.destination}",
            icon=folium.Icon(color="red", icon="flag", prefix="fa"),
        ).add_to(m)

        m.fit_bounds([[home_ll[0], home_ll[1]], [dest_ll[0], dest_ll[1]]], padding=(30, 30))
        st_folium(m, height=350, width=None, key="travel_route_map_v4", returned_objects=[])

    except Exception as e:
        st.warning(f"Could not render route map: {e}")
