"""
Climate News — agent tool.
"""

from .service import get_daily_digest, analyze_claim


def climate_news_tool(input_text: str) -> str:
    """Agent-callable tool: returns climate news digest or claim verification."""
    input_lower = input_text.lower()

    # Detect if this is a claim verification request
    claim_keywords = ["is it true", "verify", "fact-check", "fact check", "claim", "headline"]
    is_claim = any(kw in input_lower for kw in claim_keywords)

    if is_claim:
        verification = analyze_claim(input_text)
        verdict_icons = {"Verified": "✅", "Partially Verified": "⚠️", "Unverified": "❓", "False": "❌"}
        icon = verdict_icons.get(verification.verdict, "❓")

        result = f"📰 **Climate Claim Verification**\n\n"
        result += f"**Claim:** {verification.claim}\n"
        result += f"**Verdict:** {icon} {verification.verdict} (Confidence: {verification.confidence}%)\n\n"
        result += f"**Explanation:** {verification.explanation}\n"
        if verification.sources:
            result += f"\n**Sources:** {verification.sources}"
        return result
    else:
        digest = get_daily_digest()
        result = "📰 **Climate News Daily Digest**\n\n"
        for i, article in enumerate(digest.articles, 1):
            sentiment_icon = {"Alarmist": "🔴", "Balanced": "🟢", "Dismissive": "🟡"}.get(article.sentiment, "⚪")
            result += f"### {i}. {article.title}\n"
            result += f"{article.summary}\n"
            result += f"*Source: {article.source} | Reliability: {article.reliability_score}/10 | {sentiment_icon} {article.sentiment}*\n\n"
        return result
