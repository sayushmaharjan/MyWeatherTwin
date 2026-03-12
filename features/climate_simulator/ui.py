"""
Climate Simulator — Streamlit UI component.
"""

import streamlit as st
from .service import simulate_climate_scenario, SCENARIOS


def render_climate_simulator_tab(city: str):
    """Render the Climate Change Scenario Simulator tab."""
    st.subheader("🧬 Climate Change Scenario Simulator")
    st.caption("Explore future climate projections for your city")

    col1, col2, col3 = st.columns(3)
    with col1:
        sim_city = st.text_input("City", value=city, key="sim_city")
    with col2:
        scenario = st.selectbox(
            "IPCC Scenario",
            list(SCENARIOS.keys()),
            index=1,  # SSP2-4.5 default
            key="sim_scenario",
            format_func=lambda s: f"{s} — {SCENARIOS[s]}",
        )
    with col3:
        year = st.slider("Target Year", min_value=2030, max_value=2100, value=2050, step=10, key="sim_year")

    if st.button("🔬 Run Simulation", key="sim_btn", use_container_width=True):
        with st.spinner(f"Simulating {sim_city} under {scenario} for {year}..."):
            projection = simulate_climate_scenario(sim_city, scenario, year)

        # Side-by-side: today vs future
        col_today, col_future = st.columns(2)
        with col_today:
            with st.container(border=True):
                st.markdown(f"**📍 {sim_city} — Today**")
                st.caption("Current baseline conditions")
                st.markdown("Based on present-day observations")

        with col_future:
            with st.container(border=True):
                st.markdown(f"**🔮 {sim_city} — {year}**")
                st.caption(f"Scenario: {scenario}")
                st.metric("Avg High Change", projection.avg_high_change)
                st.metric("Extreme Heat Days", projection.extreme_heat_days)

        # Analog city
        with st.container(border=True):
            st.markdown(f"**🏙️ Climate Analog City**")
            st.write(f"By {year}, {sim_city}'s climate will feel most like **{projection.analog_city}** today.")

        # Narrative
        with st.container(border=True):
            st.markdown("**📖 Future Narrative**")
            st.write(projection.narrative)

        # Key impacts
        with st.container(border=True):
            st.markdown("**⚡ Key Impacts**")
            st.write(projection.key_impacts)

        st.caption(f"*Projection based on CMIP6 ensemble models under {scenario}. Uncertainty ranges apply.*")
