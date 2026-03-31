"""
Public Health Dashboard — Streamlit UI component.
Includes national heatmap, state analysis, AI summary, treatment locator,
and a dedicated public health chat (separate from the weather AI).
"""

import streamlit as st
import pandas as pd
from .service import (
    get_state_overdose_trend, get_national_heatmap_data,
    get_substance_breakdown, get_nearby_treatment_facilities,
    generate_state_summary, generate_trend_alert,
    answer_public_health_question, ensure_data_loaded,
)


US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY",
]


def render_public_health_tab():
    """Render the Public Health Dashboard tab."""

    st.markdown("""
    <div style="margin-bottom:10px;">
        <div style="font-size:1.4rem; font-weight:800; background:linear-gradient(135deg,#ef4444,#f97316);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🏥 Community Public Health Dashboard</div>
        <div style="font-size:0.72rem; color:#94a3b8; margin-top:2px;">
            Data source: CDC Drug Overdose Surveillance · SAMHSA · All data is aggregated and anonymized
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Disclaimer ────────────────────────────────
    with st.expander("ℹ️ About this dashboard"):
        st.write("""
        This dashboard displays **aggregated, anonymized public health statistics**
        from official CDC and SAMHSA sources. No individual-level data is collected
        or displayed. The goal is community awareness and resource connection —
        not surveillance.

        If you or someone you know needs help:
        **SAMHSA Helpline: 1-800-662-4357** (free, confidential, 24/7)
        """)

    # ── Data loading indicator ────────────────────
    with st.spinner("Loading public health data from CDC..."):
        try:
            ensure_data_loaded()
            data_loaded = True
        except Exception as e:
            data_loaded = False
            st.warning(f"Could not load CDC data: {e}. Some features may be limited.")

    # ── National Heatmap ──────────────────────────
    st.subheader("📍 National Overdose Overview")

    if data_loaded:
        heatmap_data = get_national_heatmap_data()
        if heatmap_data:
            try:
                import plotly.express as px
                df_map = pd.DataFrame(heatmap_data)
                fig = px.choropleth(
                    df_map,
                    locations="state",
                    locationmode="USA-states",
                    color="total_deaths",
                    scope="usa",
                    color_continuous_scale="Reds",
                    title=f"Overdose Deaths by State — {df_map['year'].iloc[0] if 'year' in df_map else 'Latest'}",
                    labels={"total_deaths": "Deaths"},
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="white",
                    geo=dict(bgcolor="rgba(0,0,0,0)"),
                    height=450,
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.info("Install `plotly` for the interactive map: `pip install plotly`")
            except Exception as e:
                st.warning(f"Could not render map: {e}")
        else:
            st.info("No heatmap data available. Data may still be loading.")

    # ── State Deep Dive ───────────────────────────
    st.divider()
    st.subheader("🔍 State-Level Analysis")

    col1, col2 = st.columns(2)
    with col1:
        default_idx = US_STATES.index("OH") if "OH" in US_STATES else 0
        selected_state = st.selectbox("Select State", US_STATES, index=default_idx,
                                      key="ph_state_select")
    with col2:
        substance_filter = st.selectbox("Substance Filter",
            ["All substances", "Opioids", "Heroin", "Fentanyl",
             "Cocaine", "Methamphetamine", "Benzodiazepines"],
            key="ph_substance_filter")
        substance_param = None if substance_filter == "All substances" else substance_filter

    if data_loaded:
        # Trend chart
        trend = get_state_overdose_trend(selected_state, substance_param)

        if "error" not in trend and trend.get("trend_data"):
            df_trend = pd.DataFrame(trend["trend_data"])
            if "year" in df_trend.columns and "month" in df_trend.columns:
                df_trend["period"] = df_trend["year"].astype(str) + "-" + df_trend["month"].astype(str).str.zfill(2)

                try:
                    import plotly.express as px
                    fig2 = px.line(
                        df_trend, x="period", y=["deaths", "rolling_avg"],
                        title=f"Monthly Overdose Deaths — {selected_state}",
                        labels={"value": "Deaths", "period": "Month", "variable": "Series"},
                        color_discrete_map={"deaths": "#ef4444", "rolling_avg": "#f97316"},
                    )
                    # Mark spike months
                    spikes = df_trend[df_trend["spike"] == True]
                    if not spikes.empty:
                        fig2.add_scatter(
                            x=spikes["period"], y=spikes["deaths"],
                            mode="markers", marker=dict(size=10, color="red", symbol="star"),
                            name="⚠️ Spike detected",
                        )
                    fig2.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="white",
                        height=350,
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                except Exception:
                    st.dataframe(df_trend[["period", "deaths", "rolling_avg"]], use_container_width=True)

            # Key metrics
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                with st.container(border=True):
                    st.metric("Avg Monthly Deaths",
                              trend["current_year_avg_monthly"] if trend["current_year_avg_monthly"] else "N/A")
            with mc2:
                with st.container(border=True):
                    yoy = trend["yoy_change_pct"]
                    st.metric("Year-over-Year Change",
                              f"{yoy}%" if yoy is not None else "N/A",
                              delta=str(yoy) if yoy else None)
            with mc3:
                with st.container(border=True):
                    st.metric("Spike Months", len(trend.get("spike_months", [])))
        else:
            st.info(f"No trend data available for {selected_state}. "
                    "This may be due to data availability from the CDC API.")

        # Substance breakdown
        breakdown = get_substance_breakdown(selected_state)
        if breakdown:
            st.divider()
            st.subheader(f"📊 Substance Breakdown — {selected_state}")
            df_breakdown = pd.DataFrame(breakdown)
            try:
                import plotly.express as px
                fig3 = px.bar(
                    df_breakdown, x="substance_type", y="total_deaths",
                    title=f"Deaths by Substance — {selected_state}",
                    color="total_deaths", color_continuous_scale="Reds",
                )
                fig3.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="white",
                    height=350,
                )
                st.plotly_chart(fig3, use_container_width=True)
            except Exception:
                st.dataframe(df_breakdown, use_container_width=True)

    # ── AI Narrative Summary ──────────────────────
    st.divider()
    st.subheader("🧠 AI Public Health Summary")

    if st.button(f"Generate Summary for {selected_state}", key="ph_gen_summary"):
        with st.spinner("Analyzing data and generating summary..."):
            summary = generate_state_summary(selected_state, substance_param)
        st.info(summary)
        st.caption("Generated from CDC official aggregate statistics · Not individual-level data")

    # ── Trend Alert ───────────────────────────────
    if data_loaded:
        try:
            alert = generate_trend_alert(selected_state)
            if alert.get("has_alert"):
                st.warning(f"⚠️ **Emerging Trend Alert — {selected_state}**\n\n{alert['alert_text']}")
        except Exception:
            pass

    # ── Treatment Resource Locator ────────────────
    st.divider()
    st.subheader("🏥 Find Treatment Resources Near You")
    st.caption("Data from SAMHSA Treatment Facility Locator — updated regularly")

    wd = st.session_state.get("weather_data")
    user_lat, user_lon = None, None
    if wd:
        city_info = wd.get("city", {})
        user_lat = city_info.get("latitude")
        user_lon = city_info.get("longitude")

    if user_lat and user_lon:
        radius = st.slider("Search radius (miles)", 5, 100, 25, key="ph_radius")
        facilities = get_nearby_treatment_facilities(user_lat, user_lon, radius)

        if facilities:
            st.write(f"Found **{len(facilities)}** facilities within {radius} miles")
            for fac in facilities:
                name = fac.get("name", fac.get("name1", "Treatment Facility"))
                dist = fac.get("distance_miles", 0)
                with st.expander(f"🏥 {name} — {dist:.1f} miles"):
                    st.write(f"**Address:** {fac.get('street1', '')}, {fac.get('city', '')}, {fac.get('state', '')}")
                    st.write(f"**Phone:** {fac.get('phone', 'Not listed')}")
                    st.write(f"**Services:** {fac.get('typeFacility', fac.get('type_facility', 'Not specified'))}")
                    if fac.get("website"):
                        st.write(f"**Website:** {fac['website']}")
        else:
            st.info("No facilities found in range, or facility data not yet loaded.")
    else:
        st.caption("ℹ️ Search for a city in the main dashboard to find nearby treatment facilities.")

    # ── Dedicated Public Health Chat ──────────────
    st.divider()
    st.markdown("""
    <div style="margin-bottom:8px;">
        <div style="font-size:1.2rem; font-weight:800; background:linear-gradient(135deg,#ef4444,#f97316);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">💬 Public Health Q&A</div>
        <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">
            Ask questions about community health data, trends, or resources.
            This chat is separate from the weather AI.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Initialize dedicated chat history (separate from weather chat)
    if "ph_chat_history" not in st.session_state:
        st.session_state.ph_chat_history = []

    # Display chat history
    for msg in st.session_state.ph_chat_history:
        role = msg["role"]
        icon = "🧑" if role == "user" else "🏥"
        align = "flex-end" if role == "user" else "flex-start"
        bg = "rgba(59,130,246,0.15)" if role == "user" else "rgba(239,68,68,0.1)"
        border_color = "rgba(59,130,246,0.3)" if role == "user" else "rgba(239,68,68,0.2)"
        st.markdown(f"""
        <div style="display:flex;justify-content:{align};margin-bottom:8px;">
            <div style="max-width:80%;background:{bg};border:1px solid {border_color};
                        border-radius:12px;padding:10px 14px;">
                <span style="font-size:0.75rem;font-weight:700;color:#94a3b8;">{icon} {'You' if role == 'user' else 'Public Health AI'}</span>
                <div style="color:#e2e8f0;font-size:0.85rem;margin-top:4px;">{msg['content']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Chat input
    ph_question = st.text_input(
        "Ask about public health data...",
        placeholder="e.g. What's the opioid situation in Ohio?",
        key="ph_chat_input",
    )

    ph_col1, ph_col2 = st.columns([1, 5])
    with ph_col1:
        send = st.button("Send", key="ph_chat_send", use_container_width=True)
    with ph_col2:
        if st.button("Clear Chat", key="ph_chat_clear"):
            st.session_state.ph_chat_history = []
            st.rerun()

    if send and ph_question:
        st.session_state.ph_chat_history.append({"role": "user", "content": ph_question})

        with st.spinner("🏥 Analyzing..."):
            answer = answer_public_health_question(ph_question, selected_state)

        st.session_state.ph_chat_history.append({"role": "assistant", "content": answer})
        st.rerun()

    # ── Crisis Resources Footer ───────────────────
    st.divider()
    st.markdown("""
    **Crisis Resources**
    - 🆘 **SAMHSA National Helpline:** 1-800-662-4357 (free, confidential, 24/7)
    - 🆘 **Crisis Text Line:** Text HOME to 741741
    - 🆘 **988 Suicide & Crisis Lifeline:** Call or text 988
    """)
