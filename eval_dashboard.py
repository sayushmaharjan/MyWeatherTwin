"""
WeatherTwin Evaluation Dashboard
==================================
Streamlit dashboard to visualize evaluation results and log analysis.

Usage:
    streamlit run eval_dashboard.py
    streamlit run eval_dashboard.py -- --results eval_results.json
"""

import json
import os
import sys
from pathlib import Path

import streamlit as st

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WeatherTwin Eval Dashboard",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Try importing plotly (required for charts) ───────────────────────────────
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.metric-card {
    background: #f8faff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
}
.metric-card .val { font-size: 1.8rem; font-weight: 700; color: #1e293b; }
.metric-card .lbl { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }

.finding-critical {
    background: #fef2f2; border-left: 4px solid #ef4444;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
}
.finding-warning {
    background: #fffbeb; border-left: 4px solid #f59e0b;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
}
.finding-info {
    background: #eff6ff; border-left: 4px solid #3b82f6;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
}
.finding-title { font-weight: 600; font-size: 0.9rem; color: #1e293b; margin-bottom: 4px; }
.finding-text  { font-size: 0.82rem; color: #475569; }
.finding-rec   { font-size: 0.82rem; color: #3b82f6; margin-top: 4px; }

.score-bar-wrap { margin-bottom: 8px; }
.score-label { font-size: 0.78rem; color: #64748b; margin-bottom: 2px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 20px;
         font-size: 0.7rem; font-weight: 600; }
.badge-primary { background: #dbeafe; color: #1d4ed8; }
.badge-small   { background: #d1fae5; color: #065f46; }
.badge-mid     { background: #fef3c7; color: #92400e; }
.badge-fast    { background: #ede9fe; color: #4c1d95; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    if not Path(path).exists():
        return {}
    with open(path) as f:
        return json.load(f)


def score_color(score: float) -> str:
    if score >= 4.0:   return "#10b981"
    elif score >= 3.0: return "#f59e0b"
    else:              return "#ef4444"


def fmt_ms(ms: float) -> str:
    if ms >= 1000:
        return f"{ms/1000:.1f}s"
    return f"{ms:.0f}ms"


def render_metric(label: str, value: str, sublabel: str = ""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="val">{value}</div>
        <div class="lbl">{label}</div>
        {"<div style='font-size:0.72rem;color:#94a3b8;margin-top:3px;'>"+sublabel+"</div>" if sublabel else ""}
    </div>""", unsafe_allow_html=True)


def render_score_bars(scores: dict, keys=None):
    keys = keys or ["accuracy", "helpfulness", "tone", "conciseness", "instruction_following"]
    for key in keys:
        val = scores.get(f"avg_{key}", scores.get(key, 0))
        pct = (val / 5) * 100
        color = score_color(val)
        st.markdown(f"""
        <div class="score-bar-wrap">
            <div class="score-label">{key.replace('_', ' ').title()}: <strong>{val:.2f}/5</strong></div>
            <div style="background:#e2e8f0;border-radius:4px;height:8px;">
                <div style="background:{color};width:{pct:.0f}%;height:8px;border-radius:4px;transition:width 0.3s;"></div>
            </div>
        </div>""", unsafe_allow_html=True)


def render_finding(f: dict):
    css_class = f"finding-{f.get('severity', 'info')}"
    icon = {"critical": "🚨", "warning": "⚠️", "info": "💡"}.get(f.get("severity"), "💡")
    st.markdown(f"""
    <div class="{css_class}">
        <div class="finding-title">{icon} [{f.get('category','')}] {f.get('finding','')}</div>
        <div class="finding-rec">→ {f.get('recommendation','')}</div>
    </div>""", unsafe_allow_html=True)


# ─── Load data ────────────────────────────────────────────────────────────────

RESULTS_FILE   = "eval_results.json"
LOG_ANALYSIS_FILE = "log_analysis.json"

eval_data = load_json(RESULTS_FILE)
log_data  = load_json(LOG_ANALYSIS_FILE)

# If log analysis is embedded in eval results, use it
if not log_data and "log_analysis" in eval_data:
    log_data = eval_data["log_analysis"]

has_eval   = bool(eval_data.get("model_summary"))
has_logs   = bool(log_data)

MODEL_COLORS = {
    "llama-3.3-70b-versatile":  "#3b82f6",
    "llama-3.1-70b-versatile":  "#10b981",
    "llama3-8b-8192":           "#f59e0b",
    "llama-3.1-8b-instant":     "#8b5cf6",
    # Legacy (deprecated on Groq — may appear in old eval_results.json)
    "gemma2-9b-it":             "#10b981",
    "mixtral-8x7b-32768":       "#ef4444",
}
MODEL_LABELS = {
    "llama-3.3-70b-versatile":  "LLaMA 3.3 70B",
    "llama-3.1-70b-versatile":  "LLaMA 3.1 70B",
    "llama3-8b-8192":           "LLaMA 3 8B",
    "llama-3.1-8b-instant":     "LLaMA 3.1 8B Instant",
    # Legacy
    "gemma2-9b-it":             "Gemma2 9B (deprecated)",
    "mixtral-8x7b-32768":       "Mixtral 8x7B (deprecated)",
}

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧪 WeatherTwin Eval")
    st.markdown("---")

    if has_eval:
        meta = eval_data.get("meta", {})
        st.success("✅ Evaluation results loaded")
        st.caption(f"Run: {meta.get('run_timestamp','')[:19]}")
        st.caption(f"Models: {len(meta.get('models_evaluated',[]))}")
        st.caption(f"Scenarios: {meta.get('scenarios_count','?')}")
    else:
        st.warning("⚠️ No eval results found")
        st.caption(f"Expected: `{RESULTS_FILE}`")
        st.caption("Run: `python evaluate.py --groq-key YOUR_KEY`")

    if has_logs:
        st.info("📋 Log analysis loaded")
    else:
        st.caption("No log_analysis.json found")

    st.markdown("---")
    page = st.radio("Navigate", [
        "📊 Overview",
        "🏆 Model Comparison",
        "📝 Scenario Explorer",
        "📋 Log Analysis",
        "🔍 Key Findings",
    ])

st.title("🧪 WeatherTwin LLM Evaluation Dashboard")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Overview
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.markdown("### At a Glance")

    if has_logs:
        llm_s = log_data.get("llm_stats", {})
        app_s = log_data.get("app_stats", {})

        cols = st.columns(5)
        with cols[0]: render_metric("Avg LLM Latency", fmt_ms(llm_s.get("avg_latency_ms", 0)), "groq / llama-3.3-70b")
        with cols[1]: render_metric("Avg Weather Fetch", fmt_ms(app_s.get("avg_latency_ms", 0)), "full pipeline")
        with cols[2]: render_metric("LLM Success Rate", f"{llm_s.get('success_rate_pct', 0)}%", f"{llm_s.get('rate_limit_errors',0)} 429 errors")
        with cols[3]: render_metric("Avg Tokens/Call", str(int(llm_s.get("avg_tokens", 0))), "proactive insight")
        with cols[4]:
            tpd = llm_s.get("tpd_utilization_pct", 0)
            render_metric("TPD Utilization", f"{tpd}%", f"of 100K limit")

    if has_eval:
        st.markdown("---")
        st.markdown("### Model Composite Scores")
        summary = eval_data.get("model_summary", {})

        if PLOTLY_OK and summary:
            model_ids = list(summary.keys())
            labels    = [MODEL_LABELS.get(m, m) for m in model_ids]
            scores    = [summary[m]["avg_composite_score"] for m in model_ids]
            colors    = [MODEL_COLORS.get(m, "#888") for m in model_ids]

            fig = go.Figure(go.Bar(
                x=labels, y=scores,
                marker_color=colors,
                text=[f"{s:.2f}" for s in scores],
                textposition="outside",
            ))
            fig.update_layout(
                yaxis=dict(title="Composite Score (1-5)", range=[0, 5.5]),
                plot_bgcolor="white",
                height=320,
                margin=dict(t=20, b=20),
                font=dict(family="Inter"),
                showlegend=False,
            )
            fig.add_hline(y=4.0, line_dash="dash", line_color="#10b981",
                          annotation_text="Good threshold (4.0)", annotation_position="right")
            st.plotly_chart(fig, use_container_width=True)
        else:
            for mid, s in summary.items():
                st.write(f"**{MODEL_LABELS.get(mid, mid)}**: {s['avg_composite_score']:.2f}/5")

    if not has_eval and not has_logs:
        st.info("No data loaded yet. Run `python evaluate.py` first, then refresh this page.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Model Comparison
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏆 Model Comparison":
    st.markdown("### Model Comparison")

    if not has_eval:
        st.warning("Run `python evaluate.py --groq-key YOUR_KEY` to generate model comparison data.")
        st.stop()

    summary = eval_data.get("model_summary", {})

    # ── Top-level metric cards ──────────────────────────────────────────────
    st.markdown("#### Quality Scores")
    cols = st.columns(len(summary))
    for i, (mid, s) in enumerate(summary.items()):
        tier_badge = f'<span class="badge badge-{s["tier"]}">{s["tier"]}</span>'
        with cols[i]:
            score = s["avg_composite_score"]
            color = score_color(score)
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size:0.75rem;color:#64748b;margin-bottom:6px;">{tier_badge}</div>
                <div style="font-size:1.6rem;font-weight:700;color:{color};">{score:.2f}<span style="font-size:1rem;color:#94a3b8;">/5</span></div>
                <div style="font-size:0.78rem;font-weight:600;color:#1e293b;margin-top:4px;">{MODEL_LABELS.get(mid, mid)}</div>
                <div style="font-size:0.7rem;color:#64748b;">{s['successful_runs']}/{s['total_runs']} successful</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Radar / Spider chart ────────────────────────────────────────────────
    if PLOTLY_OK:
        st.markdown("#### Score Breakdown (Radar)")
        score_keys = ["accuracy", "helpfulness", "tone", "conciseness", "instruction_following"]
        radar_labels = [k.replace("_", " ").title() for k in score_keys] + [score_keys[0].replace("_"," ").title()]

        fig = go.Figure()
        for mid, s in summary.items():
            vals = [s.get(f"avg_{k}", 0) for k in score_keys]
            vals_closed = vals + [vals[0]]
            fig.add_trace(go.Scatterpolar(
                r=vals_closed, theta=radar_labels,
                fill="toself", name=MODEL_LABELS.get(mid, mid),
                line=dict(color=MODEL_COLORS.get(mid, "#888"), width=2),
                fillcolor=MODEL_COLORS.get(mid, "#888"),
                opacity=0.15,
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(range=[0, 5], tickvals=[1,2,3,4,5])),
            height=420,
            font=dict(family="Inter"),
            legend=dict(orientation="h", y=-0.15),
            margin=dict(t=20, b=60),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Latency comparison ──────────────────────────────────────────────────
    st.markdown("#### Latency Comparison")
    col1, col2 = st.columns(2)

    with col1:
        if PLOTLY_OK:
            fig = go.Figure()
            for mid, s in summary.items():
                fig.add_trace(go.Bar(
                    name=MODEL_LABELS.get(mid, mid),
                    x=["Avg", "Median", "P95"],
                    y=[s["avg_latency_ms"], s["median_latency_ms"], s["p95_latency_ms"]],
                    marker_color=MODEL_COLORS.get(mid, "#888"),
                ))
            fig.update_layout(
                barmode="group",
                yaxis_title="Latency (ms)",
                height=300,
                font=dict(family="Inter"),
                plot_bgcolor="white",
                margin=dict(t=10, b=10),
                legend=dict(orientation="h", y=-0.3),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if PLOTLY_OK:
            mids  = list(summary.keys())
            labels = [MODEL_LABELS.get(m, m) for m in mids]
            tokens = [summary[m]["avg_total_tokens"] for m in mids]
            colors = [MODEL_COLORS.get(m, "#888") for m in mids]

            fig = go.Figure(go.Bar(
                x=labels, y=tokens,
                marker_color=colors,
                text=[f"{t:.0f}" for t in tokens],
                textposition="outside",
            ))
            fig.update_layout(
                title="Avg Total Tokens / Call",
                yaxis_title="Tokens",
                height=300,
                plot_bgcolor="white",
                font=dict(family="Inter"),
                showlegend=False,
                margin=dict(t=30, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Detailed per-model drill-down ───────────────────────────────────────
    st.markdown("#### Per-Model Detail")
    tabs = st.tabs([MODEL_LABELS.get(m, m) for m in summary])

    for tab, (mid, s) in zip(tabs, summary.items()):
        with tab:
            c1, c2, c3, c4 = st.columns(4)
            with c1: render_metric("Composite", f"{s['avg_composite_score']:.2f}/5")
            with c2: render_metric("Avg Latency", fmt_ms(s["avg_latency_ms"]))
            with c3: render_metric("Success Rate", f"{s['success_rate_pct']}%")
            with c4: render_metric("Avg Tokens", str(int(s["avg_total_tokens"])))

            st.markdown("**Score Breakdown:**")
            render_score_bars(s)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Scenario Explorer
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📝 Scenario Explorer":
    st.markdown("### Scenario Explorer")
    st.caption("Compare model outputs side-by-side for each test scenario.")

    if not has_eval:
        st.warning("No evaluation results found. Run `python evaluate.py --groq-key YOUR_KEY` first.")
        st.stop()

    scenario_results = eval_data.get("scenario_results", {})
    if not scenario_results:
        st.info("No scenario results in eval file.")
        st.stop()

    scenario_ids = list(scenario_results.keys())
    selected_id = st.selectbox("Select Scenario", scenario_ids)

    if selected_id:
        sr = scenario_results[selected_id]
        scenario = sr["scenario"]
        model_outputs = sr["model_outputs"]

        st.markdown("---")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f"**📍 City:** {scenario['city']}, {scenario['country']}")
            st.markdown(f"**🌡️ Temp:** {scenario['current'].get('temperature', 'N/A')}°C  |  **☁️** {scenario['current'].get('condition', 'N/A')}")
            st.markdown(f"**📊 Historical:** {scenario['historical_comparison']}")
            tags = " ".join(f"`{t}`" for t in scenario.get("tags", []))
            st.markdown(f"**🏷️ Tags:** {tags}")
        with c2:
            st.info(f"💬 **User Question:** {scenario['user_question']}")

        st.markdown("---")
        st.markdown("#### Model Responses")

        cols = st.columns(len(model_outputs))
        for col, (mid, output) in zip(cols, model_outputs.items()):
            with col:
                color = MODEL_COLORS.get(mid, "#888")
                label = MODEL_LABELS.get(mid, mid)
                scores = output.get("scores", {})
                composite = scores.get("composite", 0)

                st.markdown(f"<div style='border-top:3px solid {color};padding-top:8px;'>"
                            f"<strong>{label}</strong>"
                            f"<span style='float:right;color:{score_color(composite)};font-weight:700;'>{composite:.2f}/5</span>"
                            f"</div>", unsafe_allow_html=True)

                if output.get("success"):
                    st.caption(f"⏱ {fmt_ms(output['latency_ms'])}  |  🔢 {output.get('total_tokens',0)} tokens")
                    with st.expander("📄 Response", expanded=True):
                        st.write(output.get("response", ""))
                    if scores:
                        render_score_bars(scores, ["accuracy", "helpfulness", "tone",
                                                   "conciseness", "instruction_following"])
                        if scores.get("reasoning"):
                            st.caption(f"🤖 Judge: {scores['reasoning']}")
                else:
                    st.error(f"Failed: {output.get('error', 'Unknown')[:80]}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Log Analysis
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Log Analysis":
    st.markdown("### Log Analysis — Production Data")

    if not has_logs:
        st.warning("No log analysis data found. Run `python evaluate.py --skip-live` first.")
        st.stop()

    app_s     = log_data.get("app_stats", {})
    llm_s     = log_data.get("llm_stats", {})
    weather_s = log_data.get("weather_stats", {})

    # ── App fetch latency ────────────────────────────────────────────────────
    st.markdown("#### ⚡ Weather Fetch Latency (app.jsonl)")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: render_metric("Avg", fmt_ms(app_s.get("avg_latency_ms", 0)))
    with c2: render_metric("Median", fmt_ms(app_s.get("median_latency_ms", 0)))
    with c3: render_metric("P95", fmt_ms(app_s.get("p95_latency_ms", 0)))
    with c4: render_metric("Min", fmt_ms(app_s.get("min_latency_ms", 0)))
    with c5: render_metric("Max", fmt_ms(app_s.get("max_latency_ms", 0)))

    if PLOTLY_OK:
        all_lats = app_s.get("all_latencies_ms", [])
        if all_lats:
            fig = px.histogram(
                x=all_lats,
                nbins=20,
                labels={"x": "Latency (ms)", "y": "Count"},
                title="Latency Distribution — Full Weather Pipeline",
                color_discrete_sequence=["#3b82f6"],
            )
            fig.update_layout(
                height=260, plot_bgcolor="white",
                font=dict(family="Inter"), margin=dict(t=40, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    # Per-city latency
    city_lats = app_s.get("city_latencies", {})
    if city_lats:
        st.markdown("**Per-City Avg Latency (city search):**")
        for city, d in sorted(city_lats.items()):
            st.caption(f"  {city.title()}: {fmt_ms(d['avg_ms'])} ({d['count']} calls)")

    st.markdown("---")

    # ── LLM stats ────────────────────────────────────────────────────────────
    st.markdown("#### 🤖 LLM Performance (llm_service.jsonl)")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: render_metric("Success Rate", f"{llm_s.get('success_rate_pct',0)}%",
                            f"{llm_s.get('successful_calls',0)}/{llm_s.get('total_calls',0)} calls")
    with c2: render_metric("Avg Latency", fmt_ms(llm_s.get("avg_latency_ms", 0)), "llm only")
    with c3: render_metric("Avg Tokens", str(int(llm_s.get("avg_tokens", 0))), "per insight")
    with c4: render_metric("Rate Limit Errors", str(llm_s.get("rate_limit_errors", 0)), "429 errors")
    with c5:
        tpd = llm_s.get("tpd_utilization_pct", 0)
        color = "#ef4444" if tpd > 80 else "#f59e0b" if tpd > 50 else "#10b981"
        st.markdown(f"""
        <div class="metric-card">
            <div class="val" style="color:{color};">{tpd}%</div>
            <div class="lbl">TPD Utilization</div>
            <div style="font-size:0.72rem;color:#94a3b8;margin-top:3px;">100K token daily limit</div>
        </div>""", unsafe_allow_html=True)

    # Token usage details
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Token Stats:**")
        st.caption(f"Min tokens/call: {llm_s.get('min_tokens', 0)}")
        st.caption(f"Max tokens/call: {llm_s.get('max_tokens', 0)}")
        avg_tok = llm_s.get("avg_tokens", 1)
        if avg_tok:
            capacity = int(100000 / avg_tok)
            st.caption(f"Max insights/day at current avg: ~{capacity:,}")

    with col2:
        st.markdown("**Per-City LLM Stats:**")
        for city, s in llm_s.get("city_stats", {}).items():
            st.caption(f"{city}: {s['calls']} calls, avg {s['avg_tokens']} tokens, {fmt_ms(s['avg_latency_ms'])}")

    st.markdown("---")

    # ── Weather service breakdown ─────────────────────────────────────────────
    st.markdown("#### 🌍 Weather Service Calls (weather_service.jsonl)")
    service_counts = weather_s.get("service_call_counts", {})

    if PLOTLY_OK and service_counts:
        fig = go.Figure(go.Pie(
            labels=list(service_counts.keys()),
            values=list(service_counts.values()),
            hole=0.4,
            marker_colors=["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"],
        ))
        fig.update_layout(height=300, margin=dict(t=10, b=10), font=dict(family="Inter"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Cities with weather readings:**")
    for city, d in weather_s.get("city_weather_readings", {}).items():
        temps = d.get("temps_c", [])
        conditions = ", ".join(d.get("conditions", []))
        if temps:
            st.caption(f"  **{city}**: {d['reading_count']} readings | "
                       f"Temps: {min(temps):.1f}–{max(temps):.1f}°C | {conditions}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Key Findings
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Key Findings":
    st.markdown("### Key Findings & Recommendations")
    st.caption("Auto-generated from log analysis + evaluation results.")

    findings = []
    if has_logs:
        findings += log_data.get("key_findings", [])

    # Add eval-based findings if available
    if has_eval:
        summary = eval_data.get("model_summary", {})
        primary = summary.get("llama-3.3-70b-versatile", {})
        primary_score = primary.get("avg_composite_score", 0)
        primary_latency = primary.get("avg_latency_ms", 0)

        # Find best and worst model
        if summary:
            best_model = max(summary, key=lambda m: summary[m]["avg_composite_score"])
            worst_model = min(summary, key=lambda m: summary[m]["avg_composite_score"])
            best_score = summary[best_model]["avg_composite_score"]
            worst_score = summary[worst_model]["avg_composite_score"]

            if best_model != "llama-3.3-70b-versatile":
                findings.append({
                    "severity": "warning",
                    "category": "Model Performance",
                    "finding": f"{MODEL_LABELS.get(best_model,'?')} outscored the primary model "
                               f"({best_score:.2f} vs {primary_score:.2f}). Consider switching.",
                    "recommendation": f"Run A/B test with {MODEL_LABELS.get(best_model)} in production and measure user satisfaction.",
                })
            else:
                findings.append({
                    "severity": "info",
                    "category": "Model Performance",
                    "finding": f"llama-3.3-70b-versatile is the top performer with {primary_score:.2f}/5 composite score.",
                    "recommendation": "Continue using as primary. Monitor for regressions after Groq model updates.",
                })

            # Latency gap
            fast_model = min(summary, key=lambda m: summary[m]["avg_latency_ms"])
            fast_lat = summary[fast_model]["avg_latency_ms"]
            fast_score = summary[fast_model]["avg_composite_score"]
            if fast_model != "llama-3.3-70b-versatile" and fast_score >= primary_score - 0.3:
                findings.append({
                    "severity": "info",
                    "category": "Cost vs Speed",
                    "finding": f"{MODEL_LABELS.get(fast_model)} is {primary_latency/fast_lat:.1f}x faster "
                               f"with only {primary_score - fast_score:.2f} lower score.",
                    "recommendation": f"Use {MODEL_LABELS.get(fast_model)} for non-critical UI insights to save tokens and reduce latency.",
                })

    if not findings:
        st.info("No findings yet. Run log analysis and evaluation first.")
    else:
        critical = [f for f in findings if f.get("severity") == "critical"]
        warnings = [f for f in findings if f.get("severity") == "warning"]
        infos    = [f for f in findings if f.get("severity") == "info"]

        if critical:
            st.markdown("#### 🚨 Critical")
            for f in critical:
                render_finding(f)

        if warnings:
            st.markdown("#### ⚠️ Warnings")
            for f in warnings:
                render_finding(f)

        if infos:
            st.markdown("#### 💡 Informational")
            for f in infos:
                render_finding(f)

    st.markdown("---")
    st.markdown("#### 📌 Action Checklist")
    st.markdown("""
- [ ] Upgrade Groq to Dev Tier to remove 100K TPD rate limit
- [ ] Add exponential backoff retry in `llm_service.py`
- [ ] Cache historical weather summaries in DB (biggest latency win)
- [ ] Add model name field to `mon.record_query()` for production tracking
- [ ] Set up weekly eval re-runs when updating prompts
- [ ] Run A/B test comparing primary vs best baseline on live traffic
""")