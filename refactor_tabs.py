import os

with open("streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update tabs declaration
content = content.replace(
    'tab_dashboard, tab_compare = st.tabs(["🌍 Dashboard", "⚖️ Compare"])',
    'tab_dashboard, tab_compare, tab_health, tab_agri, tab_travel, tab_rec, tab_extreme, tab_sim, tab_news = st.tabs([\n    "🌍 Dashboard", "⚖️ Compare", "🩺 Health", "🌾 Agriculture", "✈️ Travel", "💡 Predict", "⚠️ Extreme", "🌍 Simulator", "📰 News"\n])'
)

# 2. Find the AI chat / feature block inside tab_dashboard
start_marker = "        # ─── Features & AI Chat ─────────────────────"
end_marker = "# ═══════════════════════════════════════════════════\n#  COMPARE TAB"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    feature_block = content[start_idx:end_idx]
    
    # Remove it from the current location
    content = content[:start_idx] + content[end_idx:]
    
    # Unindent from 'with tab_health:' onwards
    health_idx = feature_block.find("        with tab_health:")
    if health_idx != -1:
        tabs_content_indented = feature_block[health_idx:]
        lines = tabs_content_indented.split('\n')
        unindented_lines = []
        for line in lines:
            if line.startswith("        "):
                unindented_lines.append(line[8:])
            elif line.strip() == "":
                unindented_lines.append("")
            else:
                unindented_lines.append(line)
        
        # Prepend the city_name extraction for the feature tabs since it moved out of the data block
        tabs_content = 'city_name = st.session_state.current_city or "Unknown Location"\n\n' + "\n".join(unindented_lines)
    else:
        tabs_content = ""

    # 3. Floating chat widget code
    floating_chat_code = """
# ─── Floating AI Chat Widget ─────────────────────
st.markdown(
    \"\"\"
    <style>
    [data-testid="stPopover"] {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        z-index: 999999;
    }
    [data-testid="stPopover"] > div:first-child > button {
        border-radius: 50%;
        width: 60px;
        height: 60px;
        background: linear-gradient(135deg, #06b6d4, #3b82f6);
        color: white;
        font-size: 28px;
        border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
    }
    /* Make the popover wide enough for chat */
    div[data-testid="stPopoverBody"] {
        width: 350px !important;
        max-width: 90vw !important;
        height: 500px !important;
        max-height: 80vh !important;
        padding: 1rem;
    }
    </style>
    \"\"\",
    unsafe_allow_html=True
)

with st.popover("💬", use_container_width=False):
    st.markdown("<h4 style='margin-top:0;'>🤖 WeatherTwin AI</h4>", unsafe_allow_html=True)
    
    chat_container = st.container(height=340)
    with chat_container:
        if len(st.session_state.chat_history) == 0:
            st.caption("Ask anything about the forecast or climate impact!")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
    if prompt := st.chat_input("Ask a question..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.rerun()

# ─── Chat execution (after rerun inside the popover) ───
if len(st.session_state.chat_history) > 0 and st.session_state.chat_history[-1]["role"] == "user":
    prompt = st.session_state.chat_history[-1]["content"]
    with st.spinner("AI is thinking..."):
        groq_key = os.getenv("GROQ_API_KEY", "")
        if not groq_key or groq_key == "your_groq_api_key_here":
            answer = "⚠️ GROQ_API_KEY missing. Please check .env."
        else:
            city_name = st.session_state.current_city
            if city_name:
                try:
                    import backend.weather_service as ws
                    import backend.llm_service as llm
                    from utils import run_async
                    
                    geo = run_async(ws.geocode_city(city_name))
                    if geo:
                        cur = run_async(ws.get_current_weather(geo["latitude"], geo["longitude"]))
                        fc = run_async(ws.get_forecast(geo["latitude"], geo["longitude"], 7))
                        hist = run_async(ws.get_historical_summary(geo["latitude"], geo["longitude"], 5))
                        comp = ws.compare_to_historical(cur["temperature"], hist)
                        rag_ctx = llm.build_rag_context(geo, current=cur, forecast=fc, historical=hist, comparison=comp)
                        result = run_async(llm.chat_with_context(prompt, rag_ctx, st.session_state.chat_history[-8:-1]))
                        answer = result.get("answer", "Error resolving response.")
                        if result.get("sources"):
                            answer += f"\\n\\n*Sources: {', '.join(result['sources'])}*"
                    else:
                        answer = "I couldn't locate your selected city in the database."
                except Exception as e:
                    answer = f"Error: {e}"
            else:
                answer = "I don't have enough location data. Please search a city first!"
        
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()

"""

    content = content + "\n\n# ═══════════════════════════════════════════════════\n#  IMPORTED FEATURES\n# ═══════════════════════════════════════════════════\n" + tabs_content + "\n\n" + floating_chat_code

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
