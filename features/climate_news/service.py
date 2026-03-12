"""
Climate News — core business logic.
Daily digest, claim verification, and sentiment analysis via LLM.
"""

import json
from config import client, MODEL
from .models import NewsArticle, ClaimVerification, ClimateNewsDigest


def get_daily_digest() -> ClimateNewsDigest:
    """Generate a daily climate news digest via LLM."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a climate news analyst. Generate a JSON array of 5 current climate/weather news stories. "
                    "Each object: {\"title\": str, \"summary\": str (max 150 chars), \"source\": str, \"reliability_score\": int 1-10, \"sentiment\": \"Alarmist\"|\"Balanced\"|\"Dismissive\"}. "
                    "Reply ONLY with the JSON array."
                )},
                {"role": "user", "content": "Generate today's top 5 climate news stories."},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        text = response.choices[0].message.content.strip()
        # Parse JSON
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        raw = json.loads(text)
        articles = [NewsArticle(**item) for item in raw[:5]]
    except Exception:
        articles = []

    summary = _summarize_digest(articles)
    return ClimateNewsDigest(articles=articles, digest_summary=summary)


def analyze_claim(claim_text: str) -> ClaimVerification:
    """Fact-check a climate claim using the LLM."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a climate fact-checker. Verify the following claim against scientific data. "
                    "Reply with JSON: {\"verdict\": \"Verified\"|\"Partially Verified\"|\"Unverified\"|\"False\", "
                    "\"confidence\": int 0-100, \"explanation\": str (max 300 chars), \"sources\": str}. "
                    "Reply ONLY with JSON."
                )},
                {"role": "user", "content": f"Verify this climate claim: \"{claim_text}\""},
            ],
            temperature=0.3,
            max_tokens=250,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        data = json.loads(text)
        return ClaimVerification(claim=claim_text, **data)
    except Exception:
        return ClaimVerification(
            claim=claim_text,
            verdict="Unverified",
            confidence=0,
            explanation="Could not verify this claim.",
            sources="",
        )


def _summarize_digest(articles: list[NewsArticle]) -> str:
    """Summarize the digest in one line."""
    if not articles:
        return "No climate news available."
    titles = ", ".join(a.title for a in articles[:5])
    return f"Today's top stories: {titles}"
