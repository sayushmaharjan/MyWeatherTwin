"""
WeatherTwin — System Monitoring Dashboard
Provides real-time visibility into API performance, query analytics,
LLM metrics, and system health.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import pandas as pd

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

try:
    import monitoring as mon
    from logger_config import read_log_file, get_log_file_names, get_log_stats
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False


def render_monitoring_tab():
    """Render the full system monitoring dashboard."""

    if not MONITORING_AVAILABLE:
        st.error("⚠️ Monitoring module not available. Check backend/monitoring.py")
        return

    st.markdown("<h2 style='color:#f1f5f9;'>📊 System Monitoring Dashboard</h2>", unsafe_allow_html=True)

    # Time window selector
    col_time, col_refresh = st.columns([3, 1])
    with col_time:
        hours = st.selectbox(
            "Time Window",
            options=[1, 6, 12, 24, 48, 168],
            format_func=lambda x: f"Last {x} hour{'s' if x > 1 else ''}" if x < 24 else f"Last {x // 24} day{'s' if x > 24 else ''}",
            index=3,
            label_visibility="collapsed",
        )
    with col_refresh:
        if st.button("🔄 Refresh", use_container_width=True):
            # Force flush buffer before refresh
            try:
                mon.flush_to_database()
            except Exception:
                pass
            st.rerun()

    # ─── System Summary Cards ─────────────────
    summary = mon.get_system_summary(hours)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:16px;">
            <div style="font-size:2rem;font-weight:800;color:#3b82f6;">{summary['total_queries']}</div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">Total Queries</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        avg_resp = summary['avg_response_ms']
        resp_color = "#10b981" if avg_resp < 2000 else "#f59e0b" if avg_resp < 5000 else "#f43f5e"
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:16px;">
            <div style="font-size:2rem;font-weight:800;color:{resp_color};">{avg_resp:.0f}<span style="font-size:0.8rem;color:#64748b;">ms</span></div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">Avg Response</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:16px;">
            <div style="font-size:2rem;font-weight:800;color:#8b5cf6;">{summary['llm_calls']}</div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">LLM Calls</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        rate = summary['llm_success_rate']
        rate_color = "#10b981" if rate >= 99 else "#f59e0b" if rate >= 95 else "#f43f5e"
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:16px;">
            <div style="font-size:2rem;font-weight:800;color:{rate_color};">{rate}%</div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">LLM Success</div>
        </div>
        """, unsafe_allow_html=True)

    with c5:
        err_color = "#10b981" if summary['error_count'] == 0 else "#f59e0b" if summary['error_count'] < 5 else "#f43f5e"
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:16px;">
            <div style="font-size:2rem;font-weight:800;color:{err_color};">{summary['error_count']}</div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">Errors</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ─── Sub-tabs for detailed views ──────────
    mon_tab1, mon_tab2, mon_tab3, mon_tab4 = st.tabs([
        "📈 API Performance", "🏙️ Query Analytics", "🤖 LLM Metrics", "📋 Logs & Errors"
    ])

    # ═══ API Performance Tab ═══
    with mon_tab1:
        _render_api_performance(hours)

    # ═══ Query Analytics Tab ═══
    with mon_tab2:
        _render_query_analytics(hours)

    # ═══ LLM Metrics Tab ═══
    with mon_tab3:
        _render_llm_metrics(hours)

    # ═══ Logs & Errors Tab ═══
    with mon_tab4:
        _render_logs_and_errors(hours)


def _render_api_performance(hours: int):
    """Render API performance charts and health indicators."""
    st.markdown('<div class="wt-section-title">🌐 API Health Status</div>', unsafe_allow_html=True)

    health = mon.get_api_health(hours)

    if health:
        cols = st.columns(len(health))
        for i, (service, stats) in enumerate(health.items()):
            with cols[i]:
                st.markdown(f"""
                <div class="wt-card" style="padding:14px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                        <span style="font-size:1.2rem;">{stats['status']}</span>
                        <span style="font-weight:700;color:#f1f5f9;font-size:0.9rem;">{service}</span>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                        <div class="wt-stat">
                            <div class="wt-stat-label">Success</div>
                            <div class="wt-stat-value">{stats['success_rate']}%</div>
                        </div>
                        <div class="wt-stat">
                            <div class="wt-stat-label">Calls</div>
                            <div class="wt-stat-value">{stats['total_calls']}</div>
                        </div>
                        <div class="wt-stat">
                            <div class="wt-stat-label">Avg</div>
                            <div class="wt-stat-value">{stats['avg_latency_ms']:.0f}ms</div>
                        </div>
                        <div class="wt-stat">
                            <div class="wt-stat-label">Max</div>
                            <div class="wt-stat-value">{stats['max_latency_ms']:.0f}ms</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No API metrics recorded yet. Search for a city to generate data.")

    # Latency timeline chart
    st.markdown('<div class="wt-section-title" style="margin-top:24px;">⏱️ Response Latency Over Time</div>', unsafe_allow_html=True)

    api_metrics = mon.get_api_metrics(hours)
    if api_metrics:
        df = pd.DataFrame(api_metrics)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        fig = go.Figure()

        for service in df["service"].unique():
            sdf = df[df["service"] == service].sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=sdf["timestamp"],
                y=sdf["latency_ms"],
                name=service,
                mode="lines+markers",
                marker=dict(size=4),
                line=dict(width=2),
            ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            legend=dict(orientation="h", yanchor="bottom", y=1, xanchor="right", x=1,
                        font=dict(size=10, color="#94a3b8")),
            xaxis=dict(gridcolor="rgba(148,163,184,0.08)", tickfont=dict(size=9, color="#64748b")),
            yaxis=dict(title="Latency (ms)", gridcolor="rgba(148,163,184,0.08)",
                       tickfont=dict(size=9, color="#64748b"), title_font=dict(size=10, color="#64748b")),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No latency data available yet.")


def _render_query_analytics(hours: int):
    """Render query analytics charts."""
    analytics = mon.get_query_analytics(hours)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="wt-section-title">🏙️ Top Searched Cities</div>', unsafe_allow_html=True)

        if analytics["top_cities"]:
            cities_df = pd.DataFrame(analytics["top_cities"])
            fig = go.Figure(go.Bar(
                x=cities_df["count"],
                y=cities_df["city"],
                orientation="h",
                marker_color="rgba(59,130,246,0.7)",
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
                yaxis=dict(autorange="reversed", tickfont=dict(size=10, color="#94a3b8")),
                xaxis=dict(gridcolor="rgba(148,163,184,0.08)", tickfont=dict(size=9, color="#64748b")),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No query data yet.")

    with col2:
        st.markdown('<div class="wt-section-title">📊 Queries Over Time</div>', unsafe_allow_html=True)

        if analytics["hourly_timeline"]:
            timeline_df = pd.DataFrame(analytics["hourly_timeline"])
            timeline_df["hour"] = pd.to_datetime(timeline_df["hour"])

            fig = go.Figure(go.Bar(
                x=timeline_df["hour"],
                y=timeline_df["count"],
                marker_color="rgba(139,92,246,0.6)",
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
                xaxis=dict(gridcolor="rgba(148,163,184,0.08)", tickfont=dict(size=9, color="#64748b")),
                yaxis=dict(title="Queries", gridcolor="rgba(148,163,184,0.08)",
                           tickfont=dict(size=9, color="#64748b"), title_font=dict(size=10, color="#64748b")),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No timeline data yet.")

    # Query type breakdown
    st.markdown('<div class="wt-section-title">🔍 Query Type Distribution</div>', unsafe_allow_html=True)
    if analytics["by_type"]:
        type_df = pd.DataFrame(analytics["by_type"])
        fig = go.Figure(go.Pie(
            labels=type_df["type"],
            values=type_df["count"],
            hole=0.4,
            marker=dict(colors=["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e"]),
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
            height=250,
            legend=dict(font=dict(size=10, color="#94a3b8")),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No query type data yet.")

    # Recent queries table
    st.markdown('<div class="wt-section-title">📋 Recent Queries</div>', unsafe_allow_html=True)
    recent = mon.get_recent_queries(20)
    if recent:
        df = pd.DataFrame(recent)
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        if "response_time_ms" in df.columns:
            df["response_time_ms"] = df["response_time_ms"].apply(
                lambda x: f"{x:.0f}ms" if x else "N/A"
            )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent queries.")


def _render_llm_metrics(hours: int):
    """Render LLM performance metrics."""
    metrics = mon.get_llm_metrics(hours)

    # Summary cards
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:14px;">
            <div style="font-size:1.8rem;font-weight:800;color:#8b5cf6;">{metrics['avg_latency_ms']:.0f}<span style="font-size:0.7rem;color:#64748b;">ms</span></div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">Avg Latency</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:14px;">
            <div style="font-size:1.8rem;font-weight:800;color:#06b6d4;">{metrics['avg_tokens']:.0f}</div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">Avg Tokens/Call</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:14px;">
            <div style="font-size:1.8rem;font-weight:800;color:#3b82f6;">{metrics['total_tokens_used']:,}</div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">Total Tokens</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="wt-card" style="text-align:center;padding:14px;">
            <div style="font-size:1.4rem;font-weight:700;color:#94a3b8;">
                {metrics['min_latency_ms']:.0f} – {metrics['max_latency_ms']:.0f}<span style="font-size:0.7rem;color:#64748b;">ms</span>
            </div>
            <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:4px;">Latency Range</div>
        </div>
        """, unsafe_allow_html=True)

    # Latency timeline
    st.markdown('<div class="wt-section-title" style="margin-top:20px;">📈 LLM Latency Over Time</div>', unsafe_allow_html=True)

    if metrics["latency_timeline"]:
        df = pd.DataFrame(metrics["latency_timeline"])
        df["hour"] = pd.to_datetime(df["hour"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["hour"], y=df["avg_latency_ms"],
            mode="lines+markers",
            name="Avg Latency",
            line=dict(color="#8b5cf6", width=2),
            fill="tozeroy",
            fillcolor="rgba(139,92,246,0.1)",
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
            height=280,
            xaxis=dict(gridcolor="rgba(148,163,184,0.08)", tickfont=dict(size=9, color="#64748b")),
            yaxis=dict(title="Latency (ms)", gridcolor="rgba(148,163,184,0.08)",
                       tickfont=dict(size=9, color="#64748b"), title_font=dict(size=10, color="#64748b")),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No LLM latency data yet.")

    # Breakdown by call type
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="wt-section-title">📊 Calls by Type</div>', unsafe_allow_html=True)
        if metrics["by_type"]:
            for item in metrics["by_type"]:
                st.markdown(f"""
                <div class="wt-stat" style="margin-bottom:8px;display:flex;justify-content:space-between;padding:10px 14px;">
                    <div>
                        <span style="font-weight:600;color:#f1f5f9;">{item['type']}</span>
                        <span style="font-size:0.75rem;color:#64748b;margin-left:8px;">({item['count']} calls)</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:#8b5cf6;font-weight:600;">{item['avg_latency_ms']:.0f}ms</span>
                        <span style="font-size:0.7rem;color:#64748b;margin-left:4px;">avg</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No LLM call data yet.")

    with col2:
        st.markdown('<div class="wt-section-title">❌ Recent LLM Errors</div>', unsafe_allow_html=True)
        if metrics["recent_errors"]:
            for err in metrics["recent_errors"][:5]:
                ts = err["timestamp"][:19] if err["timestamp"] else "Unknown"
                st.markdown(f"""
                <div style="background:rgba(244,63,94,0.05);border-left:3px solid #f43f5e;
                            padding:8px 12px;border-radius:4px;margin-bottom:8px;">
                    <div style="font-size:0.7rem;color:#64748b;">{ts} · {err['call_type']}</div>
                    <div style="font-size:0.8rem;color:#f43f5e;margin-top:2px;">{err['error'][:100]}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:rgba(16,185,129,0.05);border-left:3px solid #10b981;
                        padding:10px 14px;border-radius:4px;">
                <div style="color:#10b981;font-weight:600;">✅ No LLM errors in this period</div>
            </div>
            """, unsafe_allow_html=True)


def _render_logs_and_errors(hours: int):
    """Render log viewer and error log."""

    log_tab1, log_tab2 = st.tabs(["🐛 Error Log", "📄 Application Logs"])

    with log_tab1:
        st.markdown('<div class="wt-section-title">❌ Error Log</div>', unsafe_allow_html=True)

        errors = mon.get_error_log(hours, 50)
        if errors:
            for err in errors:
                ts = err["timestamp"][:19] if err["timestamp"] else "Unknown"
                svc_color = {
                    "Groq": "#8b5cf6", "OpenMeteo": "#3b82f6",
                    "OpenWeatherMap": "#f59e0b", "Nominatim": "#06b6d4",
                    "Database": "#f43f5e",
                }.get(err["service"], "#94a3b8")

                st.markdown(f"""
                <div style="background:rgba(244,63,94,0.03);border:1px solid rgba(244,63,94,0.15);
                            border-radius:8px;padding:12px;margin-bottom:8px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <span style="background:{svc_color}22;color:{svc_color};padding:2px 8px;
                                     border-radius:4px;font-size:0.7rem;font-weight:600;">{err['service']}</span>
                        <span style="font-size:0.7rem;color:#64748b;">{ts}</span>
                        <span style="font-size:0.7rem;color:#f43f5e;font-weight:600;">{err['error_type']}</span>
                    </div>
                    <div style="font-size:0.8rem;color:#e2e8f0;">{err['message'][:200]}</div>
                </div>
                """, unsafe_allow_html=True)

                if err.get("stack_trace"):
                    with st.expander("View Stack Trace", expanded=False):
                        st.code(err["stack_trace"], language="python")
        else:
            st.success("🎉 No errors recorded in this time period!")

    with log_tab2:
        st.markdown('<div class="wt-section-title">📄 Application Logs</div>', unsafe_allow_html=True)

        log_files = get_log_file_names()
        if log_files:
            col_file, col_level, col_lines = st.columns([2, 1, 1])
            with col_file:
                selected_log = st.selectbox("Log File", log_files, label_visibility="collapsed")
            with col_level:
                level_filter = st.selectbox("Level", ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
                                            label_visibility="collapsed")
            with col_lines:
                num_lines = st.number_input("Lines", min_value=10, max_value=500,
                                            value=50, label_visibility="collapsed")

            if selected_log:
                entries = read_log_file(
                    selected_log,
                    lines=num_lines,
                    level_filter=level_filter if level_filter != "ALL" else None,
                )

                if entries:
                    for entry in entries:
                        level = entry.get("level", "INFO")
                        level_colors = {
                            "DEBUG": "#64748b", "INFO": "#10b981",
                            "WARNING": "#f59e0b", "ERROR": "#f43f5e",
                            "CRITICAL": "#f43f5e",
                        }
                        color = level_colors.get(level, "#94a3b8")
                        ts = entry.get("timestamp", "")[:19]
                        msg = entry.get("message", "")

                        extra_parts = []
                        for k in ["service", "city", "latency_ms", "tokens"]:
                            if k in entry:
                                extra_parts.append(f"{k}={entry[k]}")
                        extra_str = f" · <span style='color:#64748b;font-size:0.65rem;'>{' · '.join(extra_parts)}</span>" if extra_parts else ""

                        st.markdown(f"""
                        <div style="font-family:monospace;font-size:0.75rem;padding:3px 0;
                                    border-bottom:1px solid rgba(148,163,184,0.05);">
                            <span style="color:#64748b;">{ts}</span>
                            <span style="background:{color}22;color:{color};padding:1px 6px;
                                         border-radius:3px;font-size:0.65rem;font-weight:600;margin:0 6px;">{level}</span>
                            <span style="color:#e2e8f0;">{msg[:150]}</span>{extra_str}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No log entries match the filter.")

            # Log file stats
            st.markdown('<div class="wt-section-title" style="margin-top:20px;">📊 Log File Statistics</div>', unsafe_allow_html=True)
            stats = get_log_stats()
            if stats:
                stat_cols = st.columns(min(len(stats), 4))
                for i, (name, info) in enumerate(stats.items()):
                    with stat_cols[i % len(stat_cols)]:
                        st.markdown(f"""
                        <div class="wt-stat" style="margin-bottom:8px;">
                            <div class="wt-stat-label">📄 {name}</div>
                            <div class="wt-stat-value">{info['entries']} entries</div>
                            <div style="font-size:0.65rem;color:#64748b;">{info['size_kb']} KB</div>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("No log files found. Logs will appear after the first search.")