"""
Climate News — Streamlit UI component.
"""

import streamlit as st
from .service import get_daily_digest, analyze_claim


def render_climate_news_tab():
    """Render the Climate News Analyst tab."""
    st.subheader("📰 Climate News Analyst")
    st.caption("AI-powered climate news digest and fact-checking")

    news_tab, verify_tab = st.tabs(["📰 Daily Digest", "🔍 Fact-Check a Claim"])

    with news_tab:
        if st.button("🔄 Generate Today's Digest", key="news_digest_btn", use_container_width=True):
            with st.spinner("Compiling climate news..."):
                digest = get_daily_digest()

            if not digest.articles:
                st.info("No climate news articles available at the moment.")
            else:
                for i, article in enumerate(digest.articles, 1):
                    sentiment_colors = {"Alarmist": "delta-bad", "Balanced": "delta-good", "Dismissive": "delta-warn"}
                    with st.container(border=True):
                        col1, col2 = st.columns([5, 1])
                        with col1:
                            st.markdown(f"**{i}. {article.title}**")
                            st.write(article.summary)
                            st.caption(f"Source: {article.source}")
                        with col2:
                            st.metric("Reliability", f"{article.reliability_score}/10")
                            cls = sentiment_colors.get(article.sentiment, "delta-warn")
                            st.markdown(f'<span class="delta-chip {cls}">{article.sentiment}</span>', unsafe_allow_html=True)

    with verify_tab:
        claim_input = st.text_area(
            "Paste a climate headline or claim to verify",
            placeholder='e.g., "This was the hottest summer ever in Europe"',
            key="claim_input",
            height=80,
        )
        if st.button("🔍 Verify Claim", key="verify_btn", use_container_width=True):
            if not claim_input:
                st.warning("Please enter a claim to verify.")
            else:
                with st.spinner("Fact-checking..."):
                    verification = analyze_claim(claim_input)

                verdict_colors = {"Verified": "delta-good", "Partially Verified": "delta-warn", "Unverified": "delta-warn", "False": "delta-bad"}
                verdict_icons = {"Verified": "✅", "Partially Verified": "⚠️", "Unverified": "❓", "False": "❌"}

                with st.container(border=True):
                    st.markdown(f"**Claim:** {verification.claim}")
                    cls = verdict_colors.get(verification.verdict, "delta-warn")
                    icon = verdict_icons.get(verification.verdict, "❓")
                    st.markdown(
                        f'**Verdict:** {icon} <span class="delta-chip {cls}">{verification.verdict}</span> '
                        f'(Confidence: {verification.confidence}%)',
                        unsafe_allow_html=True,
                    )
                    st.divider()
                    st.write(verification.explanation)
                    if verification.sources:
                        st.caption(f"Sources: {verification.sources}")
