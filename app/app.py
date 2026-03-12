"""
WeatherTwin AI — Main Streamlit Application
Orchestrates all UI sections: auth, nav, weather detail, map, chat, forecast dock.
Now with tabbed navigation for 7 feature modules.
"""

import os
import sys
import json
import glob
import time
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from streamlit_folium import st_folium

# ── Ensure project root is on sys.path ──
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DEV_MODE, CHAT_CSV, LOG_FILE

from agent.tools import (
    fetch_weather,
    fetch_weather_by_coords,
    parse_current,
    predict_weather_with_bert,
)
from agent.agent_runner import run_agent, get_ai_overview, log_query

from rag.document_loader import load_weather_dataset

from app.features.auth import auth_ui
from app.features.map import create_weather_map
from app.features.forecast import render_ai_overview_and_detail, render_forecast_dock
from app.features.bert_model import load_weather_model
from app.features.logging import save_chat_to_csv, load_chat_from_csv
from app.ui.styles import inject_styles

# ── Feature module UIs ──
from features.extreme_weather.ui import render_extreme_weather_tab
from features.health_weather.ui import render_health_weather_tab
from features.agriculture.ui import render_agriculture_tab
from features.travel_planner.ui import render_travel_planner_tab
from features.climate_news.ui import render_climate_news_tab
from features.smart_recommender.ui import render_smart_recommender_tab
from features.climate_simulator.ui import render_climate_simulator_tab


# =============================================
# PAGE CONFIG
# =============================================
st.set_page_config(page_title="WeatherTwin AI", layout="wide")

# =============================================
# SESSION STATE INIT
# =============================================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None
if "sidebar_open" not in st.session_state:
    st.session_state["sidebar_open"] = True
if "show_welcome" not in st.session_state:
    st.session_state["show_welcome"] = False

# =============================================
# AUTHENTICATION CHECK
# =============================================
if DEV_MODE and st.session_state["user"] is None:
    st.session_state["user"] = "dev_user"
    st.session_state["username"] = "Say"

if st.session_state["user"] is None:
    auth_ui()
    st.stop()
else:
    if not st.session_state["show_welcome"]:
        success_placeholder = st.empty()
        success_placeholder.success(f"👋 Welcome, {st.session_state['username']}")
        time.sleep(3)
        success_placeholder.empty()
        st.session_state["show_welcome"] = True

# =============================================
# SIDEBAR LOGOUT
# =============================================
if st.session_state["user"] and st.session_state.sidebar_open:
    if st.sidebar.button("Logout"):
        st.session_state["user"] = None
        st.session_state["username"] = None
        st.session_state["show_welcome"] = False
        st.rerun()

# =============================================
# INJECT CSS
# =============================================
inject_styles()

# =============================================
# SESSION STATE (map / chat)
# =============================================
if "selected_lat" not in st.session_state:
    st.session_state.selected_lat = None
if "selected_lon" not in st.session_state:
    st.session_state.selected_lon = None
if "map_city" not in st.session_state:
    st.session_state.map_city = "New York"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = load_chat_from_csv()
if "all_plans" not in st.session_state:
    st.session_state.all_plans = [
        m for m in st.session_state.chat_history if m.get("role") == "assistant"
    ]

# =============================================
# LOAD MODELS & DATA
# =============================================
with st.spinner("Loading AI model and weather dataset..."):
    classifier = load_weather_model()
    weather_df = load_weather_dataset()

# =============================================
# TOP NAVIGATION BAR
# =============================================
bert_ok = "✓" if classifier else "✗"
nav_col1, nav_col2, nav_col3 = st.columns([2, 4, 2])
with nav_col1:
    st.markdown('<p class="nav-brand">WeatherTwin AI</p>', unsafe_allow_html=True)
with nav_col2:
    city_input = st.text_input(
        "Search",
        value=st.session_state.map_city,
        key="city_search",
        label_visibility="collapsed",
        placeholder="Search for a city...",
    )
with nav_col3:
    _n_records = len(weather_df) if weather_df is not None else 0
    _n_cities = (
        weather_df["city"].nunique()
        if weather_df is not None and "city" in weather_df.columns
        else 0
    )
    st.markdown(
        f'''<div class="nav-badges">
        <span class="nav-badge nb-green">Model: BERT {bert_ok}</span>
        <span class="nav-badge nb-blue">Records: {_n_records}</span>
        <span class="nav-badge nb-blue">Cities: {_n_cities}</span>
    </div>''',
        unsafe_allow_html=True,
    )

# Handle search
if city_input and city_input != st.session_state.map_city:
    st.session_state.map_city = city_input
    st.session_state.selected_lat = None
    st.session_state.selected_lon = None

# Fetch weather data
if st.session_state.selected_lat and st.session_state.selected_lon:
    weather_data = fetch_weather_by_coords(
        st.session_state.selected_lat, st.session_state.selected_lon
    )
else:
    weather_data = fetch_weather(st.session_state.map_city)


# =============================================
# TABBED NAVIGATION
# =============================================
tabs = st.tabs([
    "🏠 Dashboard",
    "🌪️ Extreme Weather",
    "🏥 Health Index",
    "🌾 Agriculture",
    "✈️ Travel Planner",
    "📰 Climate News",
    "🔔 Recommender",
    "🧬 Climate Simulator",
])

active_city = st.session_state.map_city


# ── TAB 0: Dashboard (original layout) ──────────
with tabs[0]:
    # AI OVERVIEW + WEATHER DETAIL
    if "error" not in weather_data:
        cur = parse_current(weather_data)
        render_ai_overview_and_detail(weather_data, cur)
    else:
        st.error(weather_data.get("error", "Could not fetch weather data."))

    # MAIN SPLIT-PANE LAYOUT
    left_pane, right_pane = st.columns([3, 2])

    # ── LEFT PANE: Chat Section ──
    @st.fragment
    def chat_section():
        with st.container(border=True):
            hdr_radio, hdr_title, hdr_actions = st.columns([2, 3, 2])
            with hdr_radio:
                query_mode = st.radio(
                    "Mode",
                    ["BERT Forecast", "Live Weather"],
                    label_visibility="collapsed",
                )
            with hdr_title:
                st.markdown("**AI Weather Assistant**")
                st.caption("Powered by BERT + Historical Data")
            with hdr_actions:
                act1, act2 = st.columns(2)
                with act1:
                    if st.button("＋ New", key="new_chat_btn", use_container_width=True):
                        for m in st.session_state.chat_history:
                            if m.get("role") == "assistant":
                                st.session_state.all_plans.append(m)
                        if os.path.exists(CHAT_CSV) and os.path.getsize(CHAT_CSV) > 0:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            archive_name = str(CHAT_CSV.parent / f"chat_log_{ts}.csv")
                            os.rename(CHAT_CSV, archive_name)
                        st.session_state.chat_history = []
                        st.rerun()
                with act2:
                    if st.button("🗑️", key="clear_chat_btn", use_container_width=True):
                        st.session_state.chat_history = []
                        if os.path.exists(CHAT_CSV):
                            os.remove(CHAT_CSV)
                        if os.path.exists(LOG_FILE):
                            os.remove(LOG_FILE)
                        st.rerun()

            st.divider()

            # Chat history (auto-scrolls)
            chat_container = st.container(height=400)
            with chat_container:
                if not st.session_state.chat_history:
                    st.markdown(
                        "<div style='text-align:center; opacity:0.4; padding:60px 0;'>"
                        "Ask me about weather anywhere.<br>Try the quick actions below!</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    for msg in st.session_state.chat_history:
                        if msg["role"] == "user":
                            st.markdown(
                                f'<div class="chat-user"><div class="chat-role">You</div>{msg["content"]}</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f'<div class="chat-ai"><div class="chat-role">WeatherTwin AI</div>{msg["content"]}</div>',
                                unsafe_allow_html=True,
                            )
                    st.markdown('<div id="chat-bottom-anchor"></div>', unsafe_allow_html=True)

            # Auto-scroll JS
            if st.session_state.chat_history:
                components.html(
                    """
                <script>
                    function scrollChat() {
                        const doc = window.parent.document;
                        const anchor = doc.getElementById('chat-bottom-anchor');
                        if (anchor) {
                            anchor.scrollIntoView({behavior: 'smooth', block: 'end'});
                        } else {
                            const containers = doc.querySelectorAll('[data-testid="stVerticalBlock"]');
                            containers.forEach(c => {
                                if (c.closest('[style*="overflow"]') || c.scrollHeight > c.clientHeight) {
                                    c.scrollTop = c.scrollHeight;
                                }
                            });
                        }
                    }
                    setTimeout(scrollChat, 200);
                    setTimeout(scrollChat, 600);
                </script>
                """,
                    height=0,
                )

            st.divider()

            # Quick Action Chips
            chip_cols = st.columns(4)
            chip_prompts = {
                "☀️ Beach Day": "What's the best beach weather this weekend in Malibu?",
                "🥾 Hiking Trip": "Is it good weather for hiking at Yosemite this weekend?",
                "🎿 Ski Conditions": "What are the skiing conditions at Lake Tahoe?",
                "🌧️ Rain Check": f"Will it rain in {st.session_state.map_city} today?",
            }
            selected_chip = None
            for i, (label, prompt) in enumerate(chip_prompts.items()):
                with chip_cols[i]:
                    if st.button(label, key=f"chip_{i}", use_container_width=True):
                        selected_chip = prompt

            # Input area
            in_col, btn_col = st.columns([7, 1])
            with in_col:
                ai_input = st.text_area(
                    "Ask",
                    key="ai_input",
                    placeholder="Plan my day around the weather...",
                    label_visibility="collapsed",
                    height=50,
                )
            with btn_col:
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                ask_clicked = st.button("→", key="ask_btn")

            final_input = selected_chip if selected_chip else (ai_input if ask_clicked else None)

            if final_input:
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": final_input,
                    "city": st.session_state.map_city,
                })
                save_chat_to_csv("user", final_input, st.session_state.map_city)

                with st.spinner("Analyzing weather data..."):
                    if "BERT" in query_mode:
                        if classifier:
                            prediction, error = predict_weather_with_bert(
                                final_input, weather_df, classifier
                            )
                            if prediction:
                                response = prediction
                                log_query(final_input, prediction, source="BERT")
                            else:
                                response = run_agent(final_input)
                        else:
                            response = run_agent(final_input)
                    else:
                        response = run_agent(final_input)

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response,
                    "city": st.session_state.map_city,
                })
                save_chat_to_csv("assistant", response, st.session_state.map_city)
                st.rerun(scope="fragment")

    with left_pane:
        chat_section()

    # ── RIGHT PANE: Map + Plans ──
    with right_pane:
        with st.container(border=True):
            st.caption("Interactive Map")
            weather_map = create_weather_map()
            map_data = st_folium(
                weather_map,
                width=None,
                height=320,
                key="weather_map",
                returned_objects=["last_clicked"],
            )
            if map_data and map_data.get("last_clicked"):
                clicked_lat = map_data["last_clicked"]["lat"]
                clicked_lon = map_data["last_clicked"]["lng"]
                if (
                    st.session_state.selected_lat != clicked_lat
                    or st.session_state.selected_lon != clicked_lon
                ):
                    st.session_state.selected_lat = clicked_lat
                    st.session_state.selected_lon = clicked_lon
                    st.rerun()

        with st.container(border=True):
            st.markdown("**Recently Generated Plans**")
            current_ai = [
                m for m in st.session_state.chat_history if m.get("role") == "assistant"
            ]
            all_plans = st.session_state.all_plans + current_ai
            seen = set()
            unique_plans = []
            for m in all_plans:
                key = m.get("content", "")[:200]
                if key not in seen:
                    seen.add(key)
                    unique_plans.append(m)
            if unique_plans:
                with st.expander(f"View {len(unique_plans)} past responses", expanded=False):
                    for idx, m in enumerate(reversed(unique_plans[-10:])):
                        preview = (
                            m["content"][:120] + "..."
                            if len(m["content"]) > 120
                            else m["content"]
                        )
                        city_tag = f' · {m.get("city", "")}' if m.get("city") else ""
                        st.caption(f"#{len(unique_plans) - idx}{city_tag}")
                        st.markdown(preview)
                        st.divider()
                if st.button("Clear All History", use_container_width=True):
                    st.session_state.chat_history = []
                    st.session_state.all_plans = []
                    if os.path.exists(CHAT_CSV):
                        os.remove(CHAT_CSV)
                    if os.path.exists(LOG_FILE):
                        os.remove(LOG_FILE)
                    for f in glob.glob(str(CHAT_CSV.parent / "chat_log_*.csv")):
                        os.remove(f)
                    st.rerun()
            else:
                st.caption("No plans generated yet. Ask the AI assistant!")

    # FIXED FORECAST DOCK
    if "weather_data" in locals() and "error" not in weather_data:
        render_forecast_dock(weather_data)


# ── TAB 1: Extreme Weather ──────────────────────
with tabs[1]:
    render_extreme_weather_tab(active_city)

# ── TAB 2: Health Index ─────────────────────────
with tabs[2]:
    render_health_weather_tab(active_city)

# ── TAB 3: Agriculture ──────────────────────────
with tabs[3]:
    render_agriculture_tab(active_city)

# ── TAB 4: Travel Planner ───────────────────────
with tabs[4]:
    render_travel_planner_tab(active_city)

# ── TAB 5: Climate News ─────────────────────────
with tabs[5]:
    render_climate_news_tab()

# ── TAB 6: Smart Recommender ────────────────────
with tabs[6]:
    render_smart_recommender_tab(active_city)

# ── TAB 7: Climate Simulator ────────────────────
with tabs[7]:
    render_climate_simulator_tab(active_city)
