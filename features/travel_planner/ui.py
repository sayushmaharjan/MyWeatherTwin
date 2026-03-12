"""
Travel Planner — Streamlit UI component.
"""

import streamlit as st
from .service import get_travel_report


def render_travel_planner_tab(city: str):
    """Render the Travel Weather Planner tab."""
    st.subheader("✈️ Travel Weather Planner")
    st.caption("Plan your trip with weather intelligence")

    col1, col2 = st.columns(2)
    with col1:
        destination = st.text_input("Destination", value=city, key="travel_dest")
    with col2:
        month = st.selectbox(
            "Month",
            ["", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"],
            key="travel_month",
        )

    if st.button("📋 Generate Travel Report", key="travel_btn", use_container_width=True):
        with st.spinner("Generating travel weather report..."):
            report = get_travel_report(destination, month)

        # Destination Profile
        with st.container(border=True):
            st.markdown("**🌤️ Destination Weather Profile**")
            st.write(report.profile)

        col_a, col_b = st.columns(2)
        with col_a:
            with st.container(border=True):
                st.markdown("**🎒 Packing Recommendations**")
                st.write(report.packing_list)
        with col_b:
            with st.container(border=True):
                st.markdown("**🔄 Weather Twin City**")
                st.write(report.weather_twin)

        with st.container(border=True):
            st.markdown("**✈️ Flight Disruption Risk**")
            st.write(report.flight_risk)
