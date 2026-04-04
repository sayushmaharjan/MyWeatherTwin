"""
Travel Planner — Streamlit UI component.
Enhanced with calendar dates, travel mode, health packing, itinerary, weather diff, and route map.
Also includes: Road Condition Predictor and Flight Delay Risk.
"""

import streamlit as st
import datetime
import pandas as pd
from .service import (
    get_travel_report, fetch_road_weather, compute_road_conditions,
    compute_flight_delay, fetch_airport_weather, parse_delay_risk,
)

def get_temp_unit():
    return st.session_state.get("temp_unit", "Celsius")

def format_temp(val_c, include_unit=True):
    if val_c is None: return "--"
    pref = get_temp_unit()
    val = (val_c * 9/5) + 32 if pref == "Fahrenheit" else val_c
    unit = ("°F" if pref == "Fahrenheit" else "°C") if include_unit else ""
    return f"{round(val)}{unit}"


# ── Airport Lookup ────────────────────────────────
AIRPORT_LOOKUP = {
    # ── Top US Airports (by passenger traffic) ──
    "Atlanta Hartsfield (ATL)": "KATL",
    "Anchorage (ANC)": "PANC",
    "Austin (AUS)": "KAUS",
    "Baltimore/Washington (BWI)": "KBWI",
    "Birmingham, AL (BHM)": "KBHM",
    "Boise (BOI)": "KBOI",
    "Boston Logan (BOS)": "KBOS",
    "Buffalo (BUF)": "KBUF",
    "Burbank (BUR)": "KBUR",
    "Charlotte (CLT)": "KCLT",
    "Chicago Midway (MDW)": "KMDW",
    "Chicago O'Hare (ORD)": "KORD",
    "Cincinnati (CVG)": "KCVG",
    "Cleveland (CLE)": "KCLE",
    "Columbus (CMH)": "KCMH",
    "Dallas Love Field (DAL)": "KDAL",
    "Dallas/Fort Worth (DFW)": "KDFW",
    "Denver (DEN)": "KDEN",
    "Detroit (DTW)": "KDTW",
    "El Paso (ELP)": "KELP",
    "Fort Lauderdale (FLL)": "KFLL",
    "Fort Myers (RSW)": "KRSW",
    "Hartford (BDL)": "KBDL",
    "Honolulu (HNL)": "PHNL",
    "Houston George Bush (IAH)": "KIAH",
    "Houston Hobby (HOU)": "KHOU",
    "Indianapolis (IND)": "KIND",
    "Jacksonville (JAX)": "KJAX",
    "JFK New York (JFK)": "KJFK",
    "Kansas City (MCI)": "KMCI",
    "Las Vegas (LAS)": "KLAS",
    "LAX Los Angeles (LAX)": "KLAX",
    "Long Beach (LGB)": "KLGB",
    "Louisville (SDF)": "KSDF",
    "Memphis (MEM)": "KMEM",
    "Miami (MIA)": "KMIA",
    "Milwaukee (MKE)": "KMKE",
    "Minneapolis (MSP)": "KMSP",
    "Nashville (BNA)": "KBNA",
    "New Orleans (MSY)": "KMSY",
    "Newark (EWR)": "KEWR",
    "LaGuardia New York (LGA)": "KLGA",
    "Norfolk (ORF)": "KORF",
    "Oakland (OAK)": "KOAK",
    "Oklahoma City (OKC)": "KOKC",
    "Omaha (OMA)": "KOMA",
    "Ontario, CA (ONT)": "KONT",
    "Orlando (MCO)": "KMCO",
    "Palm Beach (PBI)": "KPBI",
    "Philadelphia (PHL)": "KPHL",
    "Phoenix (PHX)": "KPHX",
    "Pittsburgh (PIT)": "KPIT",
    "Portland, OR (PDX)": "KPDX",
    "Providence (PVD)": "KPVD",
    "Raleigh-Durham (RDU)": "KRDU",
    "Reagan Washington (DCA)": "KDCA",
    "Dulles Washington (IAD)": "KIAD",
    "Richmond (RIC)": "KRIC",
    "Sacramento (SMF)": "KSMF",
    "Salt Lake City (SLC)": "KSLC",
    "San Antonio (SAT)": "KSAT",
    "San Diego (SAN)": "KSAN",
    "San Francisco (SFO)": "KSFO",
    "San Jose (SJC)": "KSJC",
    "Santa Ana/Orange County (SNA)": "KSNA",
    "Savannah (SAV)": "KSAV",
    "Seattle (SEA)": "KSEA",
    "St. Louis (STL)": "KSTL",
    "Tampa (TPA)": "KTPA",
    "Tucson (TUS)": "KTUS",
    "Tulsa (TUL)": "KTUL",
    # ── International Hubs ──
    "Amsterdam Schiphol (AMS)": "EHAM",
    "Cancún (CUN)": "MMUN",
    "Dubai (DXB)": "OMDB",
    "Frankfurt (FRA)": "EDDF",
    "London Heathrow (LHR)": "EGLL",
    "London Gatwick (LGW)": "EGKK",
    "Mexico City (MEX)": "MMMX",
    "Paris CDG (CDG)": "LFPG",
    "Toronto Pearson (YYZ)": "CYYZ",
    "Tokyo Narita (NRT)": "RJAA",
    "Vancouver (YVR)": "CYVR",
}

# Reverse lookup: ICAO -> display name
_ICAO_TO_NAME = {v: k for k, v in AIRPORT_LOOKUP.items()}


def _resolve_airport(user_input: str) -> tuple:
    """
    Resolve user input to (icao_code, display_label).
    Matches by: exact ICAO, 3-letter FAA code, or city name substring.
    Falls back to treating input as a raw ICAO code.
    Returns ("", "") if input is empty.
    """
    text = user_input.strip()
    if not text:
        return ("", "")
    upper = text.upper()

    # 1. Exact ICAO match (e.g. "KMCI")
    if upper in _ICAO_TO_NAME:
        return (upper, _ICAO_TO_NAME[upper])

    # 2. 3-letter FAA code → prepend K (e.g. "MCI" → "KMCI")
    if len(upper) == 3 and upper.isalpha():
        candidate = "K" + upper
        if candidate in _ICAO_TO_NAME:
            return (candidate, _ICAO_TO_NAME[candidate])
        # Not in directory but still a valid US ICAO guess
        return (candidate, f"Custom ({candidate})")

    # 3. City/airport name search (case-insensitive substring)
    lower = text.lower()
    matches = [(name, icao) for name, icao in AIRPORT_LOOKUP.items()
               if lower in name.lower()]
    if len(matches) == 1:
        return (matches[0][1], matches[0][0])
    if len(matches) > 1:
        # Return the first/best match
        return (matches[0][1], matches[0][0])

    # 4. Treat as raw ICAO code (4+ chars)
    if len(upper) >= 4 and upper.isalpha():
        return (upper, f"Custom ({upper})")

    return ("", "")


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

    # ─── Inputs — Row 1: Cities ────────────────
    city_col1, city_col2 = st.columns(2)
    with city_col1:
        departure_city = st.text_input(
            "🏠 Departure City",
            value=home_city,
            placeholder="e.g. Kansas City, New York...",
            key="travel_departure_v4",
        )
    with city_col2:
        destination = st.text_input(
            "🏙️ Destination",
            value=city or "",
            placeholder="e.g. Tokyo, Paris...",
            key="travel_dest_v4",
        )

    # ─── Inputs — Row 2: Mode + Dates ─────────
    c2, c3, c4 = st.columns([2, 2, 2])
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
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
        if health_issues:
            ctx_parts.append(f"<span style='background:rgba(244,63,94,0.15);color:#f43f5e;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;'>💊 {health_issues}</span>")
        if departure_city and departure_city != home_city:
            ctx_parts.append(f"<span style='background:rgba(59,130,246,0.15);color:#60a5fa;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;'>🏠 Home: {home_city}</span>")
        if ctx_parts:
            st.markdown(f"<div style='display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;'>{''.join(ctx_parts)}</div>", unsafe_allow_html=True)
    with btn_col:
        generate = st.button("✈️ Get Travel Plan", key="travel_gen_btn_v4", use_container_width=True)

    # ─── Generate ──────────────────────────────
    if generate:
        if not destination:
            st.error("Please enter a destination city.")
            return
        if not departure_city:
            st.error("Please enter a departure city.")
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
                home_city=departure_city,
                health_issues=health_issues,
                travel_mode=mode_clean,
            )
        st.session_state["travel_report_v4"] = report

    # ─── Display results ───────────────────────
    report = st.session_state.get("travel_report_v4")
    if report and not hasattr(report, "is_cached"):
        # Legacy object in session state, clear it
        st.session_state["travel_report_v4"] = None
        st.rerun()

    if not report:
        pass  # Don't return — still render the road/flight sections below
    else:
        # Header bar
        mode_emoji = "🚗" if report.travel_mode == "Car" else "✈️"
        is_cached_val = getattr(report, "is_cached", False)
        cache_badge = '<span style="background:rgba(16,185,129,0.1);color:#10b981;padding:2px 8px;border-radius:12px;font-size:0.6rem;font-weight:700;margin-left:10px;border:1px solid rgba(16,185,129,0.2);">⚡ CACHED</span>' if is_cached_val else ""
        
        st.markdown(f"""
<div style="background:linear-gradient(145deg,rgba(59,130,246,0.08),rgba(139,92,246,0.08));
            border:1px solid rgba(59,130,246,0.2);border-radius:12px;padding:8px 14px;margin:6px 0;display:flex;align-items:center;">
    <div style="flex-grow:1;">
        <span style="font-size:1rem;font-weight:700;color:var(--text-primary);">{mode_emoji} {report.destination}</span>
        {cache_badge}
        <div style="font-size:0.7rem;color:#94a3b8;margin-top:2px;">
            📅 {report.start_date} → {report.end_date} · {report.num_days}d · {report.travel_mode}
            {f' · 🏠 {report.home_city}' if report.home_city else ''}
        </div>
    </div>
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
            <span style="color:var(--text-secondary);font-size:0.8rem;margin-left:8px;">{report.flight_risk}</span>
        </div>
        """, unsafe_allow_html=True)

        # Route map for car
        if report.travel_mode == "Car" and report.route_coords:
            _render_route_map(report)

    # ═══════════════════════════════════════════════════
    #  NEW SECTIONS: Road Conditions + Flight Delay
    # ═══════════════════════════════════════════════════

    if "Car" in travel_mode:
        # ── 1. Road Condition Predictor ───────────────────
        st.divider()
        st.markdown("""
<div style="margin-bottom:8px;">
    <div style="font-size:1.2rem; font-weight:800; background:linear-gradient(135deg,#06b6d4,#3b82f6);
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🛣️ Road Condition Predictor</div>
    <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">Ice, fog, wind, rain, snow & full trip road safety analysis</div>
</div>
""", unsafe_allow_html=True)

        def _render_road_conditions(lat: float, lon: float, location_name: str, start_date: str = None, end_date: str = None):
            date_label = f" from {start_date} to {end_date}" if start_date and end_date else ""
            with st.spinner(f"Fetching road weather data for {location_name}{date_label}..."):
                road_data = fetch_road_weather(lat, lon, start_date=start_date, end_date=end_date)
                road = compute_road_conditions(road_data)

            if road.worst_hour:
                display_hr = road.worst_hour

                # ── Overall advisory banner ──
                st.markdown(f"""
                <div style="background:var(--secondary-background-color);border:1px solid var(--secondary-background-color);
                            border-radius:10px;padding:8px 14px;margin-bottom:8px;font-size:0.78rem;color:var(--text-color);">
                    {road.overall_advisory}
                </div>
                """, unsafe_allow_html=True)

                st.caption(f"Showing peak danger conditions at **{display_hr.time_label}**:")

                # ── Compact hazard grid (6 tiles) ──
                vis_val = f"{display_hr.fog.visibility_m:.0f}m" if display_hr.fog.visibility_m < 10000 else "10+ km"
                ice_color = "#ef4444" if display_hr.ice.risk_score >= 70 else "#f59e0b" if display_hr.ice.risk_score >= 40 else "#eab308" if display_hr.ice.risk_score >= 20 else "#22c55e"
                fog_color = "#ef4444" if display_hr.fog.density.startswith("DENSE") else "#f59e0b" if display_hr.fog.density.startswith("THICK") else "#eab308" if "FOG" in display_hr.fog.density else "#22c55e"
                wind_color = "#ef4444" if display_hr.wind.risk_score >= 60 else "#f59e0b" if display_hr.wind.risk_score >= 40 else "#eab308" if display_hr.wind.risk_score >= 20 else "#22c55e"
                rain_color = "#ef4444" if display_hr.rain.risk_score >= 60 else "#f59e0b" if display_hr.rain.risk_score >= 40 else "#eab308" if display_hr.rain.risk_score >= 20 else "#22c55e"
                temp_color = "#60a5fa" if display_hr.temp_c <= 0 else "#eab308" if display_hr.temp_c <= 5 else "#22c55e" if display_hr.temp_c <= 35 else "#ef4444"
                overall_color = "#ef4444" if display_hr.combined_danger >= 70 else "#f59e0b" if display_hr.combined_danger >= 40 else "#eab308" if display_hr.combined_danger >= 20 else "#22c55e"
                temp_icon = "❄️" if display_hr.temp_c <= 0 else "☀️"

                tile_style = "background:var(--secondary-background-color);border:1px solid var(--secondary-background-color);border-radius:8px;padding:8px 10px;text-align:center;min-width:0;"
                lbl_style = "font-size:0.65rem;color:var(--text-color);opacity:0.7;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:2px;"
                sub_style = "font-size:0.7rem;color:var(--text-color);opacity:0.85;margin-top:1px;"

                tiles = [
                    ("🧊 Ice", display_hr.ice.condition.title(), f"{display_hr.ice.icon} {display_hr.ice.risk_score}/100", ice_color),
                    ("🌫️ Fog", display_hr.fog.density.title(), f"{display_hr.fog.icon} {vis_val}", fog_color),
                    ("💨 Wind", f"{display_hr.wind.speed_kmh} km/h", f"{display_hr.wind.icon} {display_hr.wind.level.title()}", wind_color),
                    ("🌧️ Precip", display_hr.rain.level.title(), f"{display_hr.rain.icon} {display_hr.rain.precip_mm}mm", rain_color),
                    ("🌡️ Temp", format_temp(display_hr.temp_c), f"{temp_icon} Surface", temp_color),
                    ("🛣️ Overall", display_hr.overall_label.title(), f"{display_hr.overall_icon} {display_hr.combined_danger}/100", overall_color),
                ]

                tiles_html = ""
                for t_label, t_value, t_sub, t_color in tiles:
                    tiles_html += f'<div style="{tile_style}"><div style="{lbl_style}">{t_label}</div><div style="font-size:0.95rem;font-weight:700;color:{t_color};">{t_value}</div><div style="{sub_style}">{t_sub}</div></div>'

                grid_html = f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-bottom:8px;">{tiles_html}</div>'
                st.markdown(grid_html, unsafe_allow_html=True)

                # Risk factors (compact)
                if display_hr.ice.risk_factors:
                    factors_html = " · ".join(display_hr.ice.risk_factors)
                    st.markdown(f"""
                    <div style="font-size:0.7rem;color:#d97706;background:rgba(217,119,6,0.1);
                                border-radius:6px;padding:6px 10px;margin-bottom:6px;">
                        ⚠️ {factors_html}
                    </div>
                    """, unsafe_allow_html=True)

                # Driving tip
                st.caption(f"💡 {display_hr.fog.speed_advice} · Stopping distance: {display_hr.ice.stopping_distance_multiplier}x normal")

                # Peak danger alert
                total_hours = len(road.hourly)
                if road.peak_danger_score >= 40:
                    st.warning(f"⚠️ Peak danger at **{display_hr.time_label}** — Score {road.peak_danger_score}/100. "
                              f"Safe hours: {road.safe_hours_count}/{total_hours}")

                # Trip timeline (expanded with all factors)
                with st.expander("📊 Trip Road Risk Timeline"):
                    df = pd.DataFrame([{
                        "Time": r.time_label,
                        "🌡️": format_temp(r.temp_c),
                        "🧊 Ice": r.ice.risk_score,
                        "🌫️ Fog": f"{r.fog.visibility_m:.0f}m",
                        "💨 Wind": f"{r.wind.speed_kmh}",
                        "🌧️ Rain": f"{r.rain.precip_mm}mm",
                        "Overall": f"{r.overall_icon} {r.combined_danger}",
                        "Safe": "✅" if r.safe_to_drive else "⚠️"
                    } for r in road.hourly])
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info(f"Road condition data unavailable for {location_name}.")

        if report and report.home_coords and report.dest_coords:
            dep_name = report.home_city or "Departure"
            dest_name = report.destination or "Destination"
            dep_lat, dep_lon = report.home_coords
            dest_lat, dest_lon = report.dest_coords

            tab_dep, tab_dest = st.tabs([f"🛫 {dep_name}", f"🛬 {dest_name}"])

            with tab_dep:
                _render_road_conditions(dep_lat, dep_lon, dep_name, start_date=report.start_date, end_date=report.end_date)
            
            with tab_dest:
                _render_road_conditions(dest_lat, dest_lon, dest_name, start_date=report.start_date, end_date=report.end_date)
        else:
            st.caption("ℹ️ Generate a travel plan first to see road conditions for your route.")



    def _resolve_all_airports(text: str) -> list:
        if not text:
            return []
        text = text.strip()
        upper = text.upper()
        
        matches = []
        if upper in _ICAO_TO_NAME:
            matches.append((upper, _ICAO_TO_NAME[upper]))
        
        if len(upper) == 3 and upper.isalpha():
            candidate = "K" + upper
            if candidate in _ICAO_TO_NAME and candidate not in [m[0] for m in matches]:
                matches.append((candidate, _ICAO_TO_NAME[candidate]))
                
        lower = text.lower()
        for name, icao in AIRPORT_LOOKUP.items():
            if lower in name.lower() and icao not in [m[0] for m in matches]:
                matches.append((icao, name))
                
        if not matches and len(upper) >= 4 and upper.isalpha():
            matches.append((upper, f"Custom ({upper})"))
            
        return matches

    if "Flight" in travel_mode:
        # ── 3. Flight Delay Risk ──────────────────────────
        st.divider()
        st.markdown("""
        <div style="margin-bottom:8px;">
            <div style="font-size:1.2rem; font-weight:800; background:linear-gradient(135deg,#8b5cf6,#ec4899);
                 -webkit-background-clip:text; -webkit-text-fill-color:transparent;">✈️ Flight Delay Risk</div>
            <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">Real-time METAR analysis — thunderstorms, visibility, wind & de-icing queues</div>
        </div>
        """, unsafe_allow_html=True)

        if report:
            dep_city = report.home_city or "Departure"
            dest_city = report.destination or "Destination"
            
            dep_airports = _resolve_all_airports(dep_city)
            dest_airports = _resolve_all_airports(dest_city)
            
            if not dep_airports and not dest_airports:
                st.caption("ℹ️ Cannot find matching aviation airports for these cities. Try entering an airport code manually in the main search.")
            else:
                with st.spinner("Fetching aviation weather data for your route..."):
                    fl_col_dep, fl_col_dest = st.columns(2)
                    
                    with fl_col_dep:
                        st.markdown(f"**🛫 {dep_city}**")
                        if not dep_airports:
                            st.caption("No matching airports found.")
                        for icao, label in dep_airports:
                            with st.container(border=True):
                                wx = fetch_airport_weather(icao)
                                risk = parse_delay_risk(wx)
                                st.metric(f"🛫 {label} ({icao})", risk.risk_level, f"Score: {risk.delay_risk_score}/100")
                                if risk.visibility_sm is not None:
                                    st.caption(f"Visibility: {risk.visibility_sm}sm | Wind: {risk.wind_kt}kt")
                                if risk.delay_reasons:
                                    for reason in risk.delay_reasons:
                                        st.warning(reason)
                                else:
                                    st.success("✅ No significant weather delays expected")
                    
                    with fl_col_dest:
                        st.markdown(f"**🛬 {dest_city}**")
                        if not dest_airports:
                            st.caption("No matching airports found.")
                        for icao, label in dest_airports:
                            with st.container(border=True):
                                wx = fetch_airport_weather(icao)
                                risk = parse_delay_risk(wx)
                                st.metric(f"🛬 {label} ({icao})", risk.risk_level, f"Score: {risk.delay_risk_score}/100")
                                if risk.visibility_sm is not None:
                                    st.caption(f"Visibility: {risk.visibility_sm}sm | Wind: {risk.wind_kt}kt")
                                if risk.delay_reasons:
                                    for reason in risk.delay_reasons:
                                        st.warning(reason)
                                else:
                                    st.success("✅ No significant weather delays expected")
        else:
            st.caption("ℹ️ Generate a travel plan first to see real-time flight conditions for your route.")


def _render_route_map(report):
    """Render an interactive folium route map for car travel."""
    try:
        import folium
        from streamlit_folium import st_folium

        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

        if not report.home_coords or not report.dest_coords:
            st.warning("Missing coordinate data for map.")
            return

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
