"""
Smart Recommender — Streamlit UI component.
"""

import streamlit as st
from agent.tools import fetch_weather
from .service import get_smart_recommendations


def render_smart_recommender_tab(city: str):
    """Render the Smart Outfit & Activity Recommender tab."""
    st.subheader("🔔 Smart Outfit & Activity Recommender")
    st.caption(f"Personalized weather-based recommendations for **{city}**")

    with st.spinner("Generating recommendations..."):
        weather_data = fetch_weather(city)
        if "error" in weather_data:
            st.error(f"Could not fetch weather data: {weather_data['error']}")
            return
        recs = get_smart_recommendations(city, weather_data)

    categories = [
        ("👔 Outfit", recs.outfit, "Layers, rain gear, sun protection"),
        ("🏃 Exercise", recs.exercise, "Best time, indoor vs outdoor"),
        ("🚗 Commute", recs.commute, "Visibility, road conditions"),
        ("🍽️ Food", recs.food, "Hot soup day vs cold salad day"),
        ("📸 Photo Tip", recs.photo_tip, "Golden hour, cloud conditions"),
        ("🌅 Activity", recs.activity, "Beach day? Hiking? Stay in?"),
    ]

    cols = st.columns(3)
    for i, (title, content, hint) in enumerate(categories):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.write(content)
                st.caption(hint)
