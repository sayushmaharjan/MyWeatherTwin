"""
Extreme Weather — Streamlit UI component.
"""

import streamlit as st
from .service import get_extreme_weather_alerts


def render_extreme_weather_tab(city: str):
    """Render the Extreme Weather tab content."""
    st.subheader("🌪️ Extreme Weather Event Tracker")
    st.caption(f"Monitoring alerts for **{city}**")

    with st.spinner("Checking for extreme weather alerts..."):
        report = get_extreme_weather_alerts(city)

    # Overall risk badge
    risk_colors = {"Low": "delta-good", "Moderate": "delta-warn", "High": "delta-bad", "Extreme": "delta-bad"}
    risk_cls = risk_colors.get(report.overall_risk, "delta-warn")
    st.markdown(
        f'**Overall Risk:** <span class="delta-chip {risk_cls}">{report.overall_risk}</span>',
        unsafe_allow_html=True,
    )

    st.divider()

    if not report.alerts:
        st.success("✅ No active weather alerts for this location.")
    else:
        for i, alert in enumerate(report.alerts):
            severity_colors = {"Minor": "🟢", "Moderate": "🟡", "Severe": "🟠", "Extreme": "🔴"}
            icon = severity_colors.get(alert.severity, "⚪")

            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{icon} {alert.event}**")
                    st.caption(alert.headline)
                with col2:
                    st.metric("Impact", f"{alert.impact_score}/10")

                if alert.description:
                    with st.expander("View Details"):
                        st.write(alert.description)

    # Historical comparison
    st.divider()
    with st.container(border=True):
        st.markdown("**📊 Historical Comparison**")
        st.write(report.historical_comparison)
