"""
UI styles — all CSS constants for the WeatherTwin dashboard.
"""

import streamlit as st


APP_CSS = """
<style>
    :root {
        --color-humidity: #5AC8FA;
        --color-uv: #FF9F0A;
        --color-temp: #FF453A;
        --color-wind: #30D158;
        --color-pressure: #BF5AF2;
        --color-live: #32D74B;
        --color-border: rgba(164, 164, 164, 0.34);
        --radius: 12px;
    }
    /* Card padding & radius */
    [data-testid="stVerticalBlockBorderWrapper"] {
        padding: 20px !important;
        border-radius: var(--radius) !important;
        border: 1px solid var(--color-border) !important;
    }
    /* Metric styling */
    [data-testid="stMetricValue"] { font-weight: 500 !important; font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { opacity: 0.55 !important; font-weight: 600 !important; font-size: 0.78rem !important; text-transform: uppercase !important; }
    /* Glassmorphism inputs */
    [data-testid="stTextInput"] > div > div > input, .stTextArea textarea {
        background: rgba(255,255,255,0.06) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 4px !important;
        padding: 12px 16px !important;
    }
    /* Buttons */
    .stButton > button {
        border-radius: 8px !important; font-weight: 600 !important;
        transition: all 0.2s ease !important;
        border: 1px solid var(--color-border) !important;
    }
    .stButton > button:hover { transform: translateY(-1px) !important; }
    /* Nav bar */
    .top-nav { display:flex; align-items:center; justify-content:space-between; padding:8px 0 16px 0; gap:16px; flex-wrap:wrap; }
    .nav-brand { font-size:1.6rem; font-weight:700; margin:0; white-space:nowrap; }
    .nav-badges { display:flex; gap:12px; flex-shrink:0; }
    .nav-badge { display:inline-flex; align-items:center; gap:5px; padding:3px 10px; border-radius:16px; font-size:0.72rem; font-weight:600; border:1px solid rgba(255,255,255,0.08); }
    .nb-green { background:rgba(50,215,75,0.12); color:#32D74B; }
    .nb-blue { background:rgba(90,200,250,0.12); color:#5AC8FA; }
    /* Chat bubbles */
    .chat-user { background:rgba(90,200,250,0.08); border:1px solid rgba(90,200,250,0.15); border-radius:12px 12px 4px 12px; padding:12px 16px; margin:8px 0 8px 40px; }
    .chat-ai { background:rgba(255,255,255,0.04); border:1px solid var(--color-border); border-radius:12px 12px 12px 4px; padding:16px; margin:8px 40px 8px 0; }
    .chat-role { font-size:0.72rem; font-weight:600; text-transform:uppercase; opacity:0.5; margin-bottom:4px; }
    /* Quick chips */
    .chip-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px; }
    /* Delta chips */
    .delta-chip { display:inline-block; padding:2px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; margin-top:4px; }
    .delta-good { background:rgba(50,215,75,0.15); color:#32D74B; }
    .delta-warn { background:rgba(255,159,10,0.15); color:#FF9F0A; }
    .delta-bad { background:rgba(255,69,58,0.15); color:#FF453A; }
    /* Hero temp */
    .hero-temp { font-size:2.5rem !important; font-weight:400; line-height:1; margin:0; }
    .hero-condition { font-size:1.1rem; font-weight:500; opacity:0.7; margin-top:4px; }
    /* Condition card */
    .condition-card { border-radius:var(--radius); padding:16px 24px; text-align:center; color:white; text-shadow:0 1px 3px rgba(0,0,0,0.3); }
    .condition-card .icon { font-size:3rem; margin-bottom:6px; }
    .condition-card .label { font-weight:700; font-size:1rem; }
    /* Radio inline */
    [data-testid="stRadio"] > div { flex-direction:row !important; gap:8px !important; }
    /* Expander */
    [data-testid="stExpander"] { border-radius:var(--radius) !important; border:1px solid var(--color-border) !important; }
    /* Arrow button border */
    .arrow-btn button { border:1.5px solid rgba(255,255,255,0.18) !important; }
    hr { border:none !important; border-top:1px solid rgba(255,255,255,0.06) !important; margin:12px 0 !important; }

    /* Fixed Forecast Dock */
    .forecast-dock {
        position:fixed; bottom:0; left:0; right:0; z-index:9999;
        background: var(--secondary-background-color);
        color: var(--text-color);
        backdrop-filter: blur(16px);
        border-top:1px solid rgba(49, 51, 63, 0.4);
        display:flex; align-items:center; padding:0; height:90px;
    }
    .dock-label {
        min-width:180px; padding:0 20px;
        border-right:1px solid rgba(255,255,255,0.1);
        display:flex; flex-direction:column; justify-content:center; height:100%;
    }
    .dock-label-title { font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; opacity:0.6; margin-bottom:6px; }
    .dock-tabs { display:flex; gap:0; }
    .dock-tab { padding:2px 10px; font-size:0.68rem; font-weight:600; cursor:pointer; border-radius:4px; opacity:0.6; transition: all 0.15s ease; }
    .dock-tab:hover { opacity:0.7; }
    .dock-tab.active { opacity:1; background:rgba(255,255,255,0.1); }
    .dock-items {
        display:flex; flex:1; overflow-x:auto; height:100%;
    }
    .dock-item {
        flex:1; min-width:70px; display:flex; flex-direction:column;
        align-items:center; justify-content:center; gap:2px;
        border-right:1px solid rgba(255,255,255,0.05); padding:6px 4px;
    }
    .dock-item:last-child { border-right:none; }
    .dock-icon { font-size:1.4rem; }
    .dock-time { font-size:0.65rem; opacity:0.5; font-weight:600; }
    .dock-val { font-size:0.82rem; font-weight:500; }
    /* Add bottom padding to main content so dock doesn't overlap */
    [data-testid="stMain"] { padding-bottom:100px !important; }
</style>
"""


def inject_styles():
    """Inject the app-wide CSS into the Streamlit page."""
    st.markdown(APP_CSS, unsafe_allow_html=True)
