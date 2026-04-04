"""
Smart Recommender — Streamlit UI component.
"""

import streamlit as st
import asyncio
from .service import get_smart_recommendations


def run_async(coro):
    """Helper to run an async function from a synchronous context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def render_smart_recommender_tab(city: str):
    """Render the Structured Smart Daily Prediction tab."""
    
    # Custom CSS for the new premium layout
    st.markdown("""
    <style>
    .predict-container {
        color: var(--text-primary);
    }
    .summary-card {
        background: rgba(59, 130, 246, 0.05);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        border-left: 5px solid #3b82f6;
    }
    .insight-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-bottom: 24px;
    }
    .insight-card {
        background: rgba(var(--card-rgb), 0.7);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        backdrop-filter: blur(10px);
        height: 100%;
    }
    .risk-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
    }
    .risk-low { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
    .risk-moderate { background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }
    .risk-high { background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }
    
    .section-header {
        font-size: 0.8rem;
        font-weight: 700;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .bullet-list {
        margin: 0;
        padding-left: 20px;
        color: var(--text-primary);
        font-size: 0.95rem;
    }
    .bullet-item {
        margin-bottom: 8px;
    }
    .place-chip {
        display: flex;
        align-items: center;
        gap: 10px;
        background: var(--highlight);
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid var(--border-color);
        font-size: 0.95rem;
    }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("🔮 Your Personal Daily Prediction")
    st.caption(f"Synthesizing your profile with current weather for **{city}**")

    # Get data from session state
    weather_data = st.session_state.get("weather_data")
    user_profile = st.session_state.get("user_profile")

    if not weather_data:
        st.info("Please search for a city on the Dashboard to get predictions.")
        return

    with st.spinner("AI is analyzing your day..."):
        try:
            unit_p = st.session_state.get("temp_unit", "Celsius")
            recs = run_async(get_smart_recommendations(city, weather_data, user_profile, unit_p))
        except Exception as e:
            st.error(f"Prediction failed in UI: {e}")
            return

    # Determine risk class
    risk_val = (recs.risk_score or "Low").strip().lower()
    risk_class = "risk-low"
    if "moderate" in risk_val: risk_class = "risk-moderate"
    elif "high" in risk_val: risk_class = "risk-high"

    # Main Layout
    st.markdown('<div class="predict-container">', unsafe_allow_html=True)

    # 1. Smart Summary
    st.markdown(f"""
    <div class="summary-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div class="section-header">✨ Smart Summary</div>
            <div class="risk-badge {risk_class}">Risk: {recs.risk_score}</div>
        </div>
        <div style="font-size: 1.1rem; line-height: 1.5; color: var(--text-primary); font-weight: 500;">
            {recs.smart_summary}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Health & Commute Grid
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="insight-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">🏥 Health Alerts</div>', unsafe_allow_html=True)
        if recs.health_alerts:
            items = "".join([f'<li class="bullet-item">{a}</li>' for a in recs.health_alerts])
            st.markdown(f'<ul class="bullet-list">{items}</ul>', unsafe_allow_html=True)
        else:
            st.caption("No specific health risks identified.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="insight-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">🚗 Commute Insights</div>', unsafe_allow_html=True)
        if recs.commute_insights:
            items = "".join([f'<li class="bullet-item">{c}</li>' for c in recs.commute_insights])
            st.markdown(f'<ul class="bullet-list">{items}</ul>', unsafe_allow_html=True)
        else:
            st.caption("Commute looks stable.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)

    # 3. Recommendations & Places Grid
    col3, col4 = st.columns([1, 1])

    with col3:
        st.markdown('<div class="insight-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">💡 Key Recommendations</div>', unsafe_allow_html=True)
        if recs.recommendations:
            for r in recs.recommendations:
                st.markdown(f"""
                <div style="background: var(--highlight); padding: 10px; border-radius: 8px; margin-bottom: 8px; font-size: 0.9rem; border: 1px solid var(--border-color); color: var(--text-primary);">
                    {r}
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="insight-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">📍 Recommended Places</div>', unsafe_allow_html=True)
        if recs.suggested_places:
            for place in recs.suggested_places:
                st.markdown(f"""
                <div class="place-chip" style="color: var(--text-primary);">
                    <span>{place}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No specific places suggested.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
