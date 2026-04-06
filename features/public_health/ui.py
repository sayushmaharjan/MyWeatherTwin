"""
Public Health Dashboard — Streamlit UI component.
Focused on Social Media Substance Abuse Risk Analysis,
State-level Weather Correlations, and Public Health Q&A.
"""

import streamlit as st
import pandas as pd
from .service import answer_public_health_question


# Full state name → abbreviation mapping
US_STATE_NAMES = {
    "All United States": "All US",
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

# Reverse: abbreviation → full name
US_ABBR_TO_NAME = {v: k for k, v in US_STATE_NAMES.items() if v != "All US"}


def render_public_health_tab():
    """Render the Public Health Dashboard tab."""

    # Page header — clean, no gratuitous emojis
    st.markdown("""
    <div style="margin-bottom:16px;">
        <div style="font-size:1.4rem; font-weight:800;
             background:linear-gradient(135deg,#8b5cf6,#06b6d4);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
            Social Media Substance Abuse Risk Analysis
        </div>
        <div style="font-size:0.75rem; color:#94a3b8; margin-top:4px; line-height:1.5;">
            NLP analysis of Reddit posts from Hugging Face research datasets &nbsp;·&nbsp;
            Keyword + LLM risk detection &nbsp;·&nbsp; Weather correlation analysis
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("About this dashboard"):
        st.write("""
        This dashboard shows **aggregated, anonymized** results from NLP analysis of Reddit
        substance abuse discussions sourced from public Hugging Face research datasets.
        No individual-level data is collected or displayed.

        **SAMHSA Helpline:** 1-800-662-4357 (free, confidential, 24/7)
        """)

    # ── State Selection ────────────────────────────
    st.markdown("### State-Level Weather Correlation Analysis")

    state_names = list(US_STATE_NAMES.keys())   # Full names including "All United States"
    selected_name = st.selectbox(
        "Select a state to filter correlations",
        state_names,
        index=0,
        key="ph_state_select",
    )
    # Map to the abbreviation used internally
    selected_state = US_STATE_NAMES[selected_name]  # e.g. "CA" or "All US"

    _render_social_media_analysis(selected_state, selected_name)

    # ── Public Health Chat ─────────────────────────
    st.divider()

    st.markdown("""
    <div style="margin-bottom:12px;">
        <div style="font-size:1.15rem; font-weight:700; color:#e2e8f0;">
            Public Health Q&amp;A
        </div>
        <div style="font-size:0.73rem; color:#94a3b8; margin-top:3px;">
            Ask anything about the risk signals, substances, weather patterns, or community resources.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _render_chat(selected_state, selected_name)

    # ── Crisis Resources Footer ────────────────────
    st.divider()
    st.markdown("""
    **Crisis Resources**
    - SAMHSA National Helpline: **1-800-662-4357** (free, confidential, 24/7)
    - Crisis Text Line: Text **HOME** to **741741**
    - Suicide & Crisis Lifeline: Call or text **988**
    """)


def _render_chat(selected_state: str, selected_name: str):
    """Full chat interface using st.chat_message for clean message display."""

    if "ph_chat_history" not in st.session_state:
        st.session_state.ph_chat_history = []

    # Scrollable chat container — render all prior messages
    for msg in st.session_state.ph_chat_history:
        role = msg["role"]
        with st.chat_message(role, avatar="🧑" if role == "user" else "🤖"):
            st.markdown(msg["content"])

    # Chat input pinned to the bottom
    user_input = st.chat_input(
        placeholder=f"Ask about public health data for {selected_name}…",
        key="ph_chat_input_widget",
    )

    col_clear, _ = st.columns([1, 5])
    with col_clear:
        if st.button("Clear conversation", key="ph_chat_clear"):
            st.session_state.ph_chat_history = []
            st.rerun()

    if user_input:
        # Show the user message immediately
        st.session_state.ph_chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(user_input)

        # Generate and stream the response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analyzing…"):
                answer = answer_public_health_question(user_input, selected_state)
            st.markdown(answer)

        st.session_state.ph_chat_history.append({"role": "assistant", "content": answer})


# ══════════════════════════════════════════════════════════════
#  Social Media Analysis Section
# ══════════════════════════════════════════════════════════════

def _render_social_media_analysis(state_filter: str, state_name: str):
    """Render the Social Media Risk Analysis section."""

    if "sm_analysis_done" not in st.session_state:
        st.session_state.sm_analysis_done = False
    if "sm_analysis_results" not in st.session_state:
        st.session_state.sm_analysis_results = None

    col_btn, col_desc = st.columns([1, 3])
    with col_btn:
        run_analysis = st.button(
            "Run Full Analysis",
            key="sm_run_analysis",
            use_container_width=True,
            type="primary",
        )
    with col_desc:
        st.caption(
            "Loads Reddit datasets from Hugging Face, runs NLP risk detection, "
            "fetches historical weather data, and generates a comprehensive report."
        )

    if run_analysis:
        _execute_full_analysis()

    if st.session_state.sm_analysis_done and st.session_state.sm_analysis_results:
        results = st.session_state.sm_analysis_results
        df = results["df"]

        # Apply state filter
        if state_filter != "All US":
            df_filtered = df[df["location_state"] == state_filter]
        else:
            df_filtered = df

        _display_analysis_results(results, df_filtered, state_filter, state_name)


def _execute_full_analysis():
    """Execute the full analysis pipeline."""
    from .reddit_data import ensure_reddit_data, get_reddit_posts, get_dataset_summary
    from .risk_detection import analyze_posts, get_risk_summary
    from .weather_correlation import (
        fetch_weather_for_posts, compute_correlations,
        analyze_seasonal_patterns, analyze_extreme_weather_impact,
        generate_weather_insights,
    )
    from .temporal_analysis import (
        compute_temporal_trends, compute_temporal_patterns,
        cluster_posts_by_behavior, detect_emerging_narratives,
        aggregate_by_state,
    )
    from .report_generator import generate_full_report, save_report

    progress = st.progress(0, text="Loading Reddit datasets…")

    ensure_reddit_data()
    df = get_reddit_posts()
    dataset_summary = get_dataset_summary()
    progress.progress(15, text=f"Loaded {len(df)} posts. Running risk detection…")

    if df.empty:
        st.error("No Reddit data available. Check data/addiction_stories.csv")
        return

    df_analyzed = analyze_posts(df, use_llm=True)
    risk_summary = get_risk_summary(df_analyzed)
    progress.progress(40, text="Risk detection complete. Fetching weather data…")

    df_weather = fetch_weather_for_posts(df_analyzed, sample_size=80)
    correlations = compute_correlations(df_weather)
    seasonal = analyze_seasonal_patterns(df_weather)
    extreme_impact = analyze_extreme_weather_impact(df_weather)
    weather_insights = generate_weather_insights(correlations, seasonal, extreme_impact)
    progress.progress(65, text="Weather analysis complete. Computing temporal patterns…")

    temporal_trends = compute_temporal_trends(df_weather)
    temporal_patterns = compute_temporal_patterns(df_weather)
    clusters = cluster_posts_by_behavior(df_weather)
    emerging = detect_emerging_narratives(df_weather)
    state_agg = aggregate_by_state(df_weather)
    progress.progress(80, text="Generating report…")

    report = generate_full_report(
        df=df_weather,
        risk_summary=risk_summary,
        correlations=correlations,
        seasonal_analysis=seasonal,
        extreme_impact=extreme_impact,
        weather_insights=weather_insights,
        temporal_trends=temporal_trends,
        temporal_patterns=temporal_patterns,
        clusters=clusters,
        emerging_narratives=emerging,
        dataset_summary=dataset_summary,
    )
    report_path = save_report(report)
    progress.progress(100, text="Analysis complete.")

    st.session_state.sm_analysis_results = {
        "df": df_weather,
        "risk_summary": risk_summary,
        "correlations": correlations,
        "seasonal": seasonal,
        "extreme_impact": extreme_impact,
        "weather_insights": weather_insights,
        "temporal_trends": temporal_trends,
        "temporal_patterns": temporal_patterns,
        "clusters": clusters,
        "emerging": emerging,
        "state_agg": state_agg,
        "report": report,
        "report_path": report_path,
        "dataset_summary": dataset_summary,
    }
    st.session_state.sm_analysis_done = True
    st.success(f"Analysis complete. Report saved to `{report_path}`")


def _display_analysis_results(
    results: dict,
    df_filtered: pd.DataFrame,
    state_filter: str,
    state_name: str,
):
    """Display analysis results with interactive visualizations."""
    import plotly.express as px

    from .risk_detection import get_risk_summary
    from .weather_correlation import (
        compute_correlations, generate_weather_insights,
        analyze_seasonal_patterns, analyze_extreme_weather_impact,
    )

    if df_filtered.empty:
        st.info(f"No posts recorded for {state_name}. Try a different state or select 'All United States'.")
        return

    risk_summary = get_risk_summary(df_filtered)
    correlations = compute_correlations(df_filtered)
    seasonal = analyze_seasonal_patterns(df_filtered)
    extreme_impact = analyze_extreme_weather_impact(df_filtered)
    weather_insights = generate_weather_insights(correlations, seasonal, extreme_impact)
    clusters = results["clusters"]

    # ── Summary Metrics ───────────────────────────
    st.markdown(f"#### Dataset overview — {state_name}")
    m1, m2, m3 = st.columns(3)
    with m1:
        with st.container(border=True):
            st.metric("Posts analyzed", f"{risk_summary.get('total_analyzed', 0):,}")
    with m2:
        with st.container(border=True):
            st.metric("Average risk score", f"{risk_summary.get('avg_risk_score', 0):.3f}")
    with m3:
        with st.container(border=True):
            st.metric("High-risk posts", risk_summary.get("high_risk_count", 0))

    # ── Weather Correlations ───────────────────────
    st.markdown("#### Weather–substance correlations")

    insight_lines = [i for i in weather_insights if i.strip()]
    if not insight_lines or all("No statistically" in i for i in insight_lines):
        st.info(
            "No statistically significant weather-substance correlations were detected "
            "for this selection. This is common with small state-level samples."
        )
    else:
        for line in insight_lines:
            # Strip leading bullet/emoji for a cleaner look
            clean = line.lstrip("-•📊📅⚡ ").strip()
            st.markdown(f"- {clean}")

    # Scatter: Temperature vs Risk Score
    if "temperature_c" in df_filtered.columns and "risk_score" in df_filtered.columns:
        valid_df = df_filtered.dropna(subset=["temperature_c", "risk_score"])
        if len(valid_df) > 5:
            _scatter_ok = False
            # Attempt 1: OLS trendline via statsmodels (best quality)
            try:
                import statsmodels.api  # noqa — availability check
                fig_scatter = px.scatter(
                    valid_df,
                    x="temperature_c",
                    y="risk_score",
                    color="risk_severity",
                    title=f"Risk Score vs. Temperature — {state_name}",
                    labels={
                        "temperature_c": "Temperature (°C)",
                        "risk_score": "Risk Score",
                        "risk_severity": "Severity",
                    },
                    color_discrete_map={
                        "critical": "#ef4444",
                        "high": "#f97316",
                        "moderate": "#eab308",
                        "low": "#22c55e",
                        "minimal": "#94a3b8",
                    },
                    trendline="ols",
                )
                fig_scatter.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="white",
                    height=400,
                    margin=dict(t=50, b=40, l=40, r=20),
                )
                fig_scatter.update_traces(marker=dict(size=7, opacity=0.75))
                st.plotly_chart(fig_scatter, use_container_width=True)
                _scatter_ok = True
            except Exception:
                pass

            # Attempt 2: numpy-computed linear trendline — no statsmodels needed
            if not _scatter_ok:
                try:
                    import numpy as np
                    import plotly.graph_objects as go

                    x = valid_df["temperature_c"].astype(float).values
                    y = valid_df["risk_score"].astype(float).values
                    m, b = np.polyfit(x, y, 1)
                    x_line = np.linspace(x.min(), x.max(), 100)
                    y_line = m * x_line + b

                    _sev_colors = {
                        "critical": "#ef4444", "high": "#f97316",
                        "moderate": "#eab308", "low": "#22c55e", "minimal": "#94a3b8",
                    }
                    fig_scatter = go.Figure()
                    for sev, grp in valid_df.groupby("risk_severity"):
                        fig_scatter.add_trace(go.Scatter(
                            x=grp["temperature_c"], y=grp["risk_score"],
                            mode="markers", name=sev.title(),
                            marker=dict(color=_sev_colors.get(sev, "#94a3b8"),
                                        size=7, opacity=0.75),
                        ))
                    fig_scatter.add_trace(go.Scatter(
                        x=x_line, y=y_line,
                        mode="lines", name="Trend (linear)",
                        line=dict(color="rgba(255,255,255,0.6)", width=2, dash="dash"),
                    ))
                    fig_scatter.update_layout(
                        title=f"Risk Score vs. Temperature — {state_name}",
                        xaxis_title="Temperature (°C)",
                        yaxis_title="Risk Score",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="white",
                        height=400,
                        margin=dict(t=50, b=40, l=40, r=20),
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                except Exception as e2:
                    st.caption(f"Scatter chart unavailable: {e2}")

    # Seasonal bar chart
    if seasonal and "seasonal_risk" in seasonal:
        season_data = seasonal["seasonal_risk"]
        if season_data:
            try:
                season_df = pd.DataFrame([
                    {
                        "Season": k.title(),
                        "Avg Risk": round(v.get("avg_risk", 0), 3),
                        "Posts": v.get("post_count", 0),
                        "High Risk %": round(v.get("high_risk_pct", 0), 1),
                    }
                    for k, v in season_data.items()
                ])
                fig_season = px.bar(
                    season_df,
                    x="Season",
                    y="Avg Risk",
                    color="Season",
                    title=f"Average Risk Score by Season — {state_name}",
                    text="Avg Risk",
                    color_discrete_map={
                        "Winter": "#60a5fa",
                        "Spring": "#34d399",
                        "Summer": "#fbbf24",
                        "Fall": "#f97316",
                    },
                )
                fig_season.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="white",
                    height=340,
                    showlegend=False,
                    xaxis=dict(
                        categoryorder="array",
                        categoryarray=["Winter", "Spring", "Summer", "Fall"],
                    ),
                    margin=dict(t=50, b=40, l=40, r=20),
                )
                fig_season.update_traces(
                    texttemplate="%{text:.3f}",
                    textposition="outside",
                )
                st.plotly_chart(fig_season, use_container_width=True)
            except Exception as e:
                st.caption(f"Seasonal chart unavailable: {e}")

    # ── Risk Distribution ─────────────────────────
    st.markdown("#### Risk signal distribution")

    sev_col, sub_col = st.columns(2)

    with sev_col:
        sev_dist = risk_summary.get("severity_distribution", {})
        if sev_dist:
            try:
                sev_df = pd.DataFrame([
                    {"Severity": k.title(), "Count": v}
                    for k, v in sev_dist.items()
                ])
                fig_sev = px.pie(
                    sev_df,
                    values="Count",
                    names="Severity",
                    title="Severity distribution",
                    color="Severity",
                    hole=0.35,
                    color_discrete_map={
                        "Critical": "#ef4444",
                        "High": "#f97316",
                        "Moderate": "#eab308",
                        "Low": "#22c55e",
                        "Minimal": "#94a3b8",
                    },
                )
                fig_sev.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="white",
                    height=340,
                    margin=dict(t=40, b=10, l=10, r=10),
                )
                st.plotly_chart(fig_sev, use_container_width=True)
            except Exception:
                st.write(sev_dist)

    with sub_col:
        sub_dist = risk_summary.get("substance_distribution", {})
        if sub_dist:
            try:
                sub_df = pd.DataFrame([
                    {"Substance": k.replace("_", " ").title(), "Posts": v}
                    for k, v in sub_dist.items()
                ])
                fig_sub = px.bar(
                    sub_df,
                    x="Posts",
                    y="Substance",
                    orientation="h",
                    title="Substance category mentions",
                    color="Posts",
                    color_continuous_scale="Viridis",
                )
                fig_sub.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="white",
                    height=340,
                    yaxis=dict(categoryorder="total ascending"),
                    margin=dict(t=40, b=20, l=10, r=10),
                )
                st.plotly_chart(fig_sub, use_container_width=True)
            except Exception:
                st.write(sub_dist)

    # ── Behavioral Clusters (national only) ───────
    if state_filter == "All US" and clusters:
        st.markdown("#### Behavioral clusters")
        for c in clusters:
            label = f"Cluster {c['cluster_id']}: {c['cluster_label']}  —  {c['post_count']} posts · avg severity {c['avg_severity']:.3f}"
            with st.expander(label):
                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    st.write("**Dominant substances**")
                    for s in c.get("dominant_substances", []):
                        st.write(f"· {s.replace('_', ' ').title()}")
                with cc2:
                    st.write("**Top keywords**")
                    for kw in c.get("top_keywords", [])[:5]:
                        st.write(f"· `{kw}`")
                with cc3:
                    st.write(f"**Temporal pattern:** {c.get('temporal_pattern', '—')}")
                    st.write(f"**Weather context:** {c.get('weather_correlation', '—')}")
                    sev_d = c.get("severity_distribution", {})
                    if sev_d:
                        st.write("**Severity:** " + ", ".join(f"{k} {v}" for k, v in sev_d.items()))

    # ── High-Risk Posts ────────────────────────────
    st.markdown("#### High-risk post detail viewer")

    if "risk_score" in df_filtered.columns:
        high_risk_df = (
            df_filtered[df_filtered["risk_score"] >= 0.5]
            .sort_values("risk_score", ascending=False)
            .head(20)
        )

        if not high_risk_df.empty:
            sev_color_map = {
                "critical": "#ef4444", "high": "#f97316",
                "moderate": "#eab308", "low": "#22c55e", "minimal": "#94a3b8",
            }
            sev_badge = {"critical": "CRITICAL", "high": "HIGH", "moderate": "MODERATE",
                         "low": "LOW", "minimal": "MINIMAL"}

            for _, row in high_risk_df.head(10).iterrows():
                severity = row.get("risk_severity", "unknown")
                score = row.get("risk_score", 0)
                sev_colors_map = {
                    "critical": "#ef4444", "high": "#f97316",
                    "moderate": "#eab308", "low": "#22c55e", "minimal": "#94a3b8"
                }
                color = sev_colors_map.get(severity, "#94a3b8")

                body_preview = str(row.get("body", ""))[:200]
                if len(str(row.get("body", ""))) > 200:
                    body_preview += "..."

                with st.expander(
                    f"{'🔴' if severity == 'critical' else '🟠' if severity == 'high' else '🟡'} "
                    f"[{severity.upper()}] Score: {score:.3f} — "
                    f"{row.get('subreddit', '')} — {row.get('substance_categories', 'N/A')}"
                ):
                    st.markdown(f"""
                    <div style="padding:10px; background:rgba(0,0,0,0.2); border-radius:8px;
                                border-left:3px solid {color};">
                        <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:4px;">
                            {row.get('subreddit', '')} · Dataset: {row.get('source_dataset', '')}
                        </div>
                        <div style="color:#e2e8f0; font-size:0.85rem;">{body_preview}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    d1, d2 = st.columns(2)
                    with d1:
                        st.write(f"**Substances detected:** {row.get('substance_categories', '—')}")
                        st.write(f"**Signal types:** {row.get('signal_types', '—')}")
                    with d2:
                        st.write(f"**Keywords matched:** {row.get('keywords_matched', '—')}")
                        if row.get("explanation"):
                            st.write(f"**Analysis:** {row['explanation']}")
        else:
            st.info("No high-risk posts detected for this selection.")

    # ── Report Download (national only) ───────────
    if state_filter == "All US":
        st.markdown("#### Full analysis report")
        report = results.get("report", "")
        if report:
            st.download_button(
                label="Download full report (Markdown)",
                data=report,
                file_name="substance_abuse_risk_report.md",
                mime="text/markdown",
                key="sm_download_report",
                use_container_width=True,
            )
            with st.expander("Preview report"):
                st.markdown(report[:3000] + "\n\n*(download for full report)*")
