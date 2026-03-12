"""
Forecast rendering — 12-hour forecast dock and weather detail card.
"""

import json
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta

from agent.tools import parse_current
from agent.agent_runner import get_ai_overview
from app.ui.components import weather_to_icon, condition_icon_simple


def render_ai_overview_and_detail(weather_data, cur):
    """Render the AI Overview (left) + Weather Detail Card (right) section."""
    overview_col, detail_col = st.columns([2, 3])

    # ── LEFT: AI Overview ──
    with overview_col:
        with st.container(border=True):
            st.markdown("**🤖 AI Weather Overview**")
            st.caption(f"{cur['city']} · {cur['localtime']}")
            weather_json_str = json.dumps({
                "city": cur["city"],
                "temp_c": cur["temp_c"],
                "condition": cur["condition"],
                "humidity": cur["humidity"],
                "wind_kph": cur["wind_kph"],
                "uv": cur["uv"],
                "vis_km": cur["vis_km"],
                "sunrise": cur["sunrise"],
                "sunset": cur["sunset"],
            })
            with st.spinner("Generating overview..."):
                overview_text = get_ai_overview(weather_json_str)
            st.markdown(
                f'<div style="font-size:1.05rem; line-height:1.6; padding:8px 0;">{overview_text}</div>',
                unsafe_allow_html=True,
            )

    # ── RIGHT: Weather Detail Card ──
    with detail_col:
        with st.container(border=True):
            hero_col, toggle_col = st.columns([5, 1])
            with toggle_col:
                use_imperial = st.toggle("°F", key="unit_toggle")

            if use_imperial:
                temp_val = f"{(cur['temp_c'] * 9/5) + 32:.1f}"
                temp_unit = "°F"
                wind_disp = f"{cur['wind_kph'] * 0.621371:.1f} mph"
                vis_disp = f"{cur['vis_km'] * 0.621371:.1f} mi"
                press_disp = f"{cur['pressure_mb'] * 0.02953:.2f} inHg"
            else:
                temp_val = f"{cur['temp_c']}"
                temp_unit = "°C"
                wind_disp = f"{cur['wind_kph']} km/h"
                vis_disp = f"{cur['vis_km']} km"
                press_disp = f"{cur['pressure_mb']} mb"

            ic = condition_icon_simple(cur["condition"])

            with hero_col:
                st.markdown(f"""<div style="display:flex; align-items:center; gap:16px;">
                    <div>
                        <p class="hero-temp">{temp_val}<span style="font-size:2rem; opacity:0.6;">{temp_unit}</span></p>
                        <p class="hero-condition">{ic} {cur['condition']}</p>
                    </div>
                    <div style="opacity:0.6; font-size:0.85rem;">
                        {cur['city']}, {cur['region']}<br>{cur['localtime']}
                    </div>
                </div>""", unsafe_allow_html=True)

            # 6 metric tiles
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1:
                st.metric("Humidity", f"{cur['humidity']}%")
                h_cls = "delta-good" if cur['humidity'] < 60 else ("delta-warn" if cur['humidity'] < 80 else "delta-bad")
                h_lbl = "Normal" if cur['humidity'] < 60 else ("High" if cur['humidity'] < 80 else "Very High")
                st.markdown(f'<span class="delta-chip {h_cls}">{h_lbl}</span>', unsafe_allow_html=True)
            with c2:
                st.metric("Wind", wind_disp)
                w_cls = "delta-good" if cur['wind_kph'] < 20 else ("delta-warn" if cur['wind_kph'] < 50 else "delta-bad")
                w_lbl = "Calm" if cur['wind_kph'] < 20 else ("Breezy" if cur['wind_kph'] < 50 else "Strong")
                st.markdown(f'<span class="delta-chip {w_cls}">{w_lbl}</span>', unsafe_allow_html=True)
            with c3:
                uv_val = float(cur['uv']) if str(cur['uv']).replace('.', '', 1).isdigit() else 0
                st.metric("UV Index", cur['uv'])
                uv_cls = "delta-good" if uv_val <= 2 else ("delta-warn" if uv_val <= 7 else "delta-bad")
                uv_lbl = "Low" if uv_val <= 2 else ("Moderate" if uv_val <= 5 else "High")
                st.markdown(f'<span class="delta-chip {uv_cls}">{uv_lbl}</span>', unsafe_allow_html=True)
            with c4:
                st.metric("Pressure", press_disp)
                p_val = cur['pressure_mb']
                p_cls = "delta-good" if 1000 <= p_val <= 1025 else ("delta-warn" if 980 <= p_val < 1000 or 1025 < p_val <= 1040 else "delta-bad")
                p_lbl = "Normal" if 1000 <= p_val <= 1025 else ("Low" if p_val < 1000 else "High")
                st.markdown(f'<span class="delta-chip {p_cls}">{p_lbl}</span>', unsafe_allow_html=True)
            with c5:
                st.metric("Visibility", vis_disp)
                v_val = cur['vis_km']
                v_cls = "delta-good" if v_val >= 10 else ("delta-warn" if v_val >= 5 else "delta-bad")
                v_lbl = "Clear" if v_val >= 10 else ("Moderate" if v_val >= 5 else "Poor")
                st.markdown(f'<span class="delta-chip {v_cls}">{v_lbl}</span>', unsafe_allow_html=True)
            with c6:
                aqi_raw = cur.get('aqi', 'N/A')
                st.metric("AQI", aqi_raw)
                if str(aqi_raw).isdigit():
                    aqi_v = int(aqi_raw)
                    a_cls = "delta-good" if aqi_v <= 2 else ("delta-warn" if aqi_v <= 4 else "delta-bad")
                    a_lbl = "Good" if aqi_v <= 2 else ("Moderate" if aqi_v <= 4 else "Unhealthy")
                    st.markdown(f'<span class="delta-chip {a_cls}">{a_lbl}</span>', unsafe_allow_html=True)


def render_forecast_dock(weather_data):
    """Render the fixed forecast dock bar at the bottom of the page."""
    current_time_str = weather_data["location"]["localtime"]
    current_time = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M")
    end_time = current_time + timedelta(hours=12)

    sunrise_str = weather_data["forecast"]["forecastday"][0]["astro"]["sunrise"]
    sunset_str = weather_data["forecast"]["forecastday"][0]["astro"]["sunset"]
    sunrise = datetime.strptime(f"{current_time.date()} {sunrise_str}", "%Y-%m-%d %I:%M %p")
    sunset = datetime.strptime(f"{current_time.date()} {sunset_str}", "%Y-%m-%d %I:%M %p")

    all_hours = []
    for day in weather_data["forecast"]["forecastday"]:
        all_hours.extend(day["hour"])

    _imperial = st.session_state.get("unit_toggle", False)
    forecast_items = []
    for h in all_hours:
        h_time = datetime.strptime(h["time"], "%Y-%m-%d %H:%M")
        if current_time <= h_time <= end_time:
            ic = weather_to_icon(h["condition"]["text"], h_time, sunrise, sunset)
            if _imperial:
                t_display = f"{(h['temp_c'] * 9/5) + 32:.0f}°F"
            else:
                t_display = f"{h['temp_c']:.0f}°C"
            forecast_items.append({
                "time": h_time.strftime("%H:%M"),
                "icon": ic,
                "temp": t_display,
                "humidity": f"{h['humidity']}%",
            })

    items_html = ""
    for item in forecast_items:
        items_html += f'''<div class="dock-item">
            <span class="dock-icon">{item["icon"]}</span>
            <span class="dock-val dock-val-temp">{item["temp"]}</span>
            <span class="dock-val dock-val-hum" style="display:none;">{item["humidity"]}</span>
            <span class="dock-time">{item["time"]}</span>
        </div>'''

    st.markdown(f'''
    <div class="forecast-dock">
        <div class="dock-label">
            <span class="dock-label-title">12-HOUR FORECAST</span>
            <div class="dock-tabs">
                <span class="dock-tab active" id="dock-tab-temp">Temp</span>
                <span class="dock-tab" id="dock-tab-hum">Humidity</span>
            </div>
        </div>
        <div class="dock-items">{items_html}</div>
    </div>
    ''', unsafe_allow_html=True)

    # JS for dock tab toggling
    components.html('''
    <script>
        function setupDockToggle() {
            const doc = window.parent.document;
            const tabTemp = doc.getElementById('dock-tab-temp');
            const tabHum = doc.getElementById('dock-tab-hum');

            if (!tabTemp || !tabHum) {
                setTimeout(setupDockToggle, 100);
                return;
            }

            if (tabTemp.dataset.bound) return;
            tabTemp.dataset.bound = 'true';

            tabTemp.addEventListener('click', function() {
                doc.querySelectorAll('.dock-val-temp').forEach(el => el.style.display = 'inline');
                doc.querySelectorAll('.dock-val-hum').forEach(el => el.style.display = 'none');
                tabTemp.classList.add('active');
                tabHum.classList.remove('active');
            });

            tabHum.addEventListener('click', function() {
                doc.querySelectorAll('.dock-val-temp').forEach(el => el.style.display = 'none');
                doc.querySelectorAll('.dock-val-hum').forEach(el => el.style.display = 'inline');
                tabHum.classList.add('active');
                tabTemp.classList.remove('active');
            });
        }
        setupDockToggle();
    </script>
    ''', height=0)
