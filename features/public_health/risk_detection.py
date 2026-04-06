"""
Risk Signal Detection Engine — NLP + LLM-powered substance abuse risk analysis.

Detects:
  1. Direct substance mentions (alcohol, drugs, tobacco, etc.)
  2. Emotional distress / relapse signals
  3. Indirect mentions, slang, metaphors, emojis
  4. Ranks by severity (minimal → low → moderate → high → critical)
"""

import re
import json
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime

from config import sync_client, MODEL

# ═══════════════════════════════════════════════════
#  Substance Lexicons
# ═══════════════════════════════════════════════════

SUBSTANCE_LEXICONS = {
    "alcohol": {
        "direct": ["alcohol", "beer", "wine", "vodka", "whiskey", "liquor", "bourbon",
                    "tequila", "rum", "gin", "cocktail", "drinking", "drunk", "hangover",
                    "blackout", "binge drinking", "dui", "alcoholic", "alcoholism",
                    "booze", "brew", "shots", "bar", "pub"],
        "slang": ["sauce", "liquid courage", "hair of the dog", "on the wagon",
                  "off the wagon", "falling off", "hitting the bottle", "tipsy",
                  "hammered", "wasted", "plastered", "sloshed", "lit", "buzzed",
                  "three sheets", "liquid lunch", "nightcap", "cold one", "brewski"],
        "emoji": ["🍺", "🍻", "🍷", "🍸", "🍹", "🥃", "🍾", "🥂"],
    },
    "opioids": {
        "direct": ["opioid", "heroin", "fentanyl", "morphine", "oxycodone", "hydrocodone",
                    "codeine", "tramadol", "methadone", "suboxone", "buprenorphine",
                    "percocet", "vicodin", "oxycontin", "dilaudid", "opiate"],
        "slang": ["oxy", "percs", "blues", "roxies", "h", "smack", "dope", "tar",
                  "china white", "needle", "nod", "nodding off", "on the nod",
                  "kick", "kicking", "cold turkey", "jones", "jonesing", "fix",
                  "shooting up", "mainlining", "chasing the dragon"],
        "emoji": ["💉", "💊"],
    },
    "cannabis": {
        "direct": ["marijuana", "cannabis", "weed", "thc", "cbd", "edible", "edibles",
                    "dispensary", "joint", "blunt", "bong", "dab", "vape cartridge"],
        "slang": ["pot", "grass", "herb", "mary jane", "mj", "420", "ganja", "kush",
                  "loud", "dank", "chronic", "stoned", "baked", "blazed", "toking",
                  "puff", "smoke out", "green", "trees", "flower"],
        "emoji": ["🍃", "🌿", "💨", "🌲"],
    },
    "stimulants": {
        "direct": ["cocaine", "crack", "methamphetamine", "amphetamine", "adderall",
                    "ritalin", "vyvanse", "modafinil", "mdma", "ecstasy", "molly",
                    "stimulant"],
        "slang": ["coke", "blow", "snow", "meth", "crystal", "ice", "speed", "crank",
                  "tina", "glass", "uppers", "addies", "study drugs", "rails",
                  "lines", "bumps", "8ball", "tweaking", "geeked", "wired",
                  "rolling", "e", "x"],
        "emoji": ["❄️", "⚡", "💎"],
    },
    "benzodiazepines": {
        "direct": ["benzodiazepine", "xanax", "valium", "klonopin", "ativan",
                    "lorazepam", "diazepam", "alprazolam", "clonazepam", "benzo"],
        "slang": ["bars", "xans", "benzos", "footballs", "handlebars", "planks",
                  "ladders", "school bus", "yellow bus", "zan", "zannies"],
        "emoji": ["💊"],
    },
    "tobacco_nicotine": {
        "direct": ["tobacco", "nicotine", "cigarette", "smoking", "vaping", "vape",
                    "juul", "e-cigarette", "cigar", "chewing tobacco", "snuff",
                    "hookah", "nicotine patch", "nicotine gum"],
        "slang": ["cigs", "smokes", "stogie", "dip", "chew", "nic", "pod",
                  "clouds", "hitting the vape", "nic sick", "chain smoking"],
        "emoji": ["🚬", "💨"],
    },
    "general_substance": {
        "direct": ["substance abuse", "addiction", "addicted", "substance use",
                    "drug abuse", "drug use", "drug problem", "rehab", "rehabilitation",
                    "detox", "withdrawal", "overdose", "od", "relapse", "recovery",
                    "sober", "sobriety", "clean", "abstinence", "dependence",
                    "tolerance", "12 step", "aa", "na", "sponsor"],
        "slang": ["using", "user", "junkie", "fiend", "strung out", "coming down",
                  "crashed", "checked in", "habit", "monkey on my back",
                  "fell off the wagon", "white knuckling", "one day at a time",
                  "slippery slope", "rock bottom", "wake up call"],
        "emoji": ["⚠️", "🆘", "🏥"],
    },
}

# ═══════════════════════════════════════════════════
#  Emotional Distress Lexicon
# ═══════════════════════════════════════════════════

DISTRESS_LEXICONS = {
    "depression": ["depressed", "depression", "hopeless", "worthless", "empty",
                   "numb", "can't feel", "don't care anymore", "give up",
                   "what's the point", "no reason to live", "tired of everything",
                   "darkness", "dark place", "hole", "drowning", "sinking"],
    "anxiety": ["anxious", "anxiety", "panic", "panic attack", "worried",
                "can't breathe", "racing thoughts", "overwhelmed", "terrified",
                "dread", "on edge", "restless", "can't sleep", "insomnia"],
    "frustration": ["frustrated", "angry", "rage", "pissed", "sick of",
                    "fed up", "can't take it", "breaking point", "snapped",
                    "losing it", "going crazy", "had enough"],
    "hopelessness": ["hopeless", "no hope", "never get better", "stuck",
                     "trapped", "no way out", "dead end", "pointless",
                     "meaningless", "why bother", "giving up", "surrender"],
    "relapse": ["relapse", "relapsed", "slipped", "slip up", "fell off",
                "went back", "used again", "couldn't resist", "caved",
                "broke my streak", "back to day one", "reset", "failed",
                "day 0", "starting over"],
    "crisis": ["suicidal", "suicide", "kill myself", "end it", "self harm",
               "cutting", "hurt myself", "don't want to be here",
               "can't go on", "last resort", "goodbye letter", "final"],
}

DISTRESS_EMOJI = ["😢", "😭", "😔", "😞", "💔", "🥺", "😰", "😨", "😱",
                  "🆘", "⚠️", "❌", "💀", "🖤", "😵", "🤯"]


# ═══════════════════════════════════════════════════
#  Keyword-based Detection
# ═══════════════════════════════════════════════════

def detect_substance_keywords(text: str) -> List[Dict]:
    """Fast keyword-based substance detection."""
    text_lower = text.lower()
    signals = []

    for category, lexicon in SUBSTANCE_LEXICONS.items():
        matched_keywords = []

        # Check direct terms
        for term in lexicon["direct"]:
            if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                matched_keywords.append(term)

        # Check slang
        for term in lexicon["slang"]:
            if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                matched_keywords.append(term)

        # Check emoji
        for emoji in lexicon.get("emoji", []):
            if emoji in text:
                matched_keywords.append(emoji)

        if matched_keywords:
            # Extract evidence snippet
            evidence = _extract_evidence(text, matched_keywords[0])
            signals.append({
                "signal_type": "substance_mention",
                "substance_category": category,
                "keywords_matched": matched_keywords,
                "evidence": evidence,
                "keyword_count": len(matched_keywords),
            })

    return signals


def detect_distress_keywords(text: str) -> List[Dict]:
    """Fast keyword-based emotional distress detection."""
    text_lower = text.lower()
    signals = []

    for category, keywords in DISTRESS_LEXICONS.items():
        matched = []
        for term in keywords:
            if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                matched.append(term)

        # Check distress emoji
        emoji_matched = [e for e in DISTRESS_EMOJI if e in text]

        if matched or emoji_matched:
            evidence = _extract_evidence(text, (matched + emoji_matched)[0])
            signals.append({
                "signal_type": "emotional_distress",
                "substance_category": category,
                "keywords_matched": matched + emoji_matched,
                "evidence": evidence,
                "keyword_count": len(matched) + len(emoji_matched),
            })

    return signals


def _extract_evidence(text: str, keyword: str, window: int = 100) -> str:
    """Extract a context window around the first occurrence of a keyword."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return text[:200]

    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end].strip()

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


# ═══════════════════════════════════════════════════
#  Severity Scoring
# ═══════════════════════════════════════════════════

def compute_severity(signals: List[Dict], text: str) -> tuple:
    """
    Composite severity scoring based on:
    - Number and type of signals
    - Presence of crisis language
    - Co-occurrence of substance + distress signals
    - Active vs. passive language

    Returns (severity_label, severity_score)
    """
    if not signals:
        return "minimal", 0.0

    text_lower = text.lower()

    # Base score from signal count
    total_keywords = sum(s.get("keyword_count", 0) for s in signals)
    base_score = min(total_keywords * 0.08, 0.4)

    # Signal type multipliers
    has_substance = any(s["signal_type"] == "substance_mention" for s in signals)
    has_distress = any(s["signal_type"] == "emotional_distress" for s in signals)
    has_crisis = any(s.get("substance_category") == "crisis" for s in signals)
    has_relapse = any(s.get("substance_category") == "relapse" for s in signals)

    # Co-occurrence bonus (substance + distress is higher risk)
    if has_substance and has_distress:
        base_score += 0.2

    # Crisis signals are always high severity
    if has_crisis:
        base_score += 0.4

    # Relapse signals
    if has_relapse:
        base_score += 0.15

    # Active use language (first person, present tense)
    active_patterns = [
        r"\bi\s+(am|was|have been)\s+(using|drinking|smoking|snorting|shooting)",
        r"\bi\s+(used|drank|smoked|relapsed|overdosed)",
        r"\bi\s+can'?t\s+(stop|quit|resist)",
        r"\bi\s+(need|want)\s+(a\s+)?(drink|fix|hit|high|dose)",
    ]
    for pattern in active_patterns:
        if re.search(pattern, text_lower):
            base_score += 0.1

    # Hard substance bonus
    hard_substances = {"opioids", "stimulants", "benzodiazepines"}
    if any(s.get("substance_category") in hard_substances for s in signals):
        base_score += 0.1

    # Cap at 1.0
    score = min(base_score, 1.0)

    # Map to label
    if score >= 0.8:
        label = "critical"
    elif score >= 0.6:
        label = "high"
    elif score >= 0.4:
        label = "moderate"
    elif score >= 0.2:
        label = "low"
    else:
        label = "minimal"

    return label, round(score, 3)


# ═══════════════════════════════════════════════════
#  LLM-Enhanced Analysis (batch)
# ═══════════════════════════════════════════════════

RISK_ANALYSIS_PROMPT = """You are an expert public health NLP analyst specializing in substance abuse risk detection from social media text.

Analyze the following batch of social media posts for substance abuse risk signals. For each post, provide:
1. substance_categories: list of detected substance types (alcohol, opioids, cannabis, stimulants, benzodiazepines, tobacco_nicotine, general_substance, none)
2. distress_level: none, mild, moderate, severe  
3. risk_severity: minimal, low, moderate, high, critical
4. key_signals: list of key phrases/terms that indicate risk
5. explanation: 1-2 sentence explanation of risk assessment
6. confidence: 0.0-1.0

Focus on detecting:
- Direct and indirect substance mentions including slang, street names, metaphors
- Emotional distress co-occurring with substance discussion
- Relapse signals  
- Active use vs recovery discussion
- Crisis indicators

Respond ONLY with a valid JSON array. No markdown. No extra text.

Posts to analyze:
"""


def llm_analyze_batch(posts: List[Dict], batch_size: int = 10) -> List[Dict]:
    """
    Use LLM for enhanced risk analysis on a batch of posts.
    Falls back to keyword-only analysis if LLM fails.
    """
    results = []

    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        batch_text = ""
        for idx, post in enumerate(batch):
            text = post.get("body", "") or post.get("title", "")
            text = text[:500]  # Truncate for token efficiency
            batch_text += f"\n[POST {idx + 1}] (id: {post['post_id']})\n{text}\n"

        try:
            response = sync_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": RISK_ANALYSIS_PROMPT},
                    {"role": "user", "content": batch_text},
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            content = response.choices[0].message.content.strip()
            # Clean potential markdown wrapping
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            parsed = json.loads(content)
            if isinstance(parsed, list):
                results.extend(parsed)
            else:
                results.append(parsed)

        except Exception as e:
            print(f"⚠️ LLM batch analysis failed: {e}")
            # Create placeholder results for failed batch
            for post in batch:
                results.append({
                    "substance_categories": [],
                    "distress_level": "unknown",
                    "risk_severity": "unknown",
                    "key_signals": [],
                    "explanation": "LLM analysis unavailable",
                    "confidence": 0.0,
                })

    return results


# ═══════════════════════════════════════════════════
#  Main Analysis Pipeline
# ═══════════════════════════════════════════════════

def analyze_posts(df: pd.DataFrame, use_llm: bool = True) -> pd.DataFrame:
    """
    Full risk signal analysis pipeline.

    For each post:
    1. Run keyword-based detection
    2. Compute composite severity
    3. Optionally enhance with LLM analysis

    Returns DataFrame with risk analysis columns added.
    """
    print(f"🔍 Analyzing {len(df)} posts for risk signals...")

    all_signals = []
    severity_labels = []
    severity_scores = []
    substance_categories = []
    signal_types = []
    evidence_list = []
    keywords_list = []
    explanations = []
    confidences = []

    for idx, row in df.iterrows():
        text = str(row.get("body", "")) + " " + str(row.get("title", ""))
        text = text.strip()

        if not text or text == "nan nan":
            # No text to analyze
            all_signals.append([])
            severity_labels.append("minimal")
            severity_scores.append(0.0)
            substance_categories.append("")
            signal_types.append("")
            evidence_list.append("")
            keywords_list.append("")
            explanations.append("No text content")
            confidences.append(0.0)
            continue

        # Keyword detection
        substance_signals = detect_substance_keywords(text)
        distress_signals = detect_distress_keywords(text)
        combined_signals = substance_signals + distress_signals

        # Severity scoring
        severity, score = compute_severity(combined_signals, text)

        # Aggregate results
        cats = list(set(s["substance_category"] for s in substance_signals))
        types = list(set(s["signal_type"] for s in combined_signals))
        kws = []
        for s in combined_signals:
            kws.extend(s.get("keywords_matched", []))
        evs = [s.get("evidence", "") for s in combined_signals[:2]]

        all_signals.append(combined_signals)
        severity_labels.append(severity)
        severity_scores.append(score)
        substance_categories.append(", ".join(cats) if cats else "none")
        signal_types.append(", ".join(types) if types else "none")
        evidence_list.append(" | ".join(evs)[:500] if evs else "")
        keywords_list.append(", ".join(list(set(kws))[:10]))
        explanations.append("")
        confidences.append(0.7 if combined_signals else 0.3)

    # Add columns
    df = df.copy()
    df["risk_severity"] = severity_labels
    df["risk_score"] = severity_scores
    df["substance_categories"] = substance_categories
    df["signal_types"] = signal_types
    df["evidence"] = evidence_list
    df["keywords_matched"] = keywords_list
    df["explanation"] = explanations
    df["confidence"] = confidences

    # LLM enhancement for moderate+ posts
    if use_llm:
        high_risk_mask = df["risk_score"] >= 0.3
        high_risk_posts = df[high_risk_mask].to_dict("records")

        if high_risk_posts:
            print(f"🧠 Running LLM analysis on {len(high_risk_posts)} medium/high-risk posts...")
            llm_results = llm_analyze_batch(high_risk_posts, batch_size=8)

            # Merge LLM results back
            hr_indices = df.index[high_risk_mask].tolist()
            for i, (idx, result) in enumerate(zip(hr_indices, llm_results)):
                if isinstance(result, dict):
                    llm_severity = result.get("risk_severity", "")
                    if llm_severity and llm_severity != "unknown":
                        # Blend LLM severity with keyword severity
                        severity_map = {"minimal": 0.1, "low": 0.25, "moderate": 0.5, "high": 0.75, "critical": 0.95}
                        llm_score = severity_map.get(llm_severity, 0.3)
                        keyword_score = df.at[idx, "risk_score"]
                        blended = round(0.4 * keyword_score + 0.6 * llm_score, 3)
                        df.at[idx, "risk_score"] = blended

                        # Re-label from blended score
                        if blended >= 0.8:
                            df.at[idx, "risk_severity"] = "critical"
                        elif blended >= 0.6:
                            df.at[idx, "risk_severity"] = "high"
                        elif blended >= 0.4:
                            df.at[idx, "risk_severity"] = "moderate"
                        elif blended >= 0.2:
                            df.at[idx, "risk_severity"] = "low"
                        else:
                            df.at[idx, "risk_severity"] = "minimal"

                    if result.get("explanation"):
                        df.at[idx, "explanation"] = result["explanation"]
                    if result.get("confidence"):
                        df.at[idx, "confidence"] = result["confidence"]

                    # Merge LLM substance categories
                    llm_cats = result.get("substance_categories", [])
                    if llm_cats and llm_cats != ["none"]:
                        existing = df.at[idx, "substance_categories"]
                        existing_set = set(existing.split(", ")) if existing and existing != "none" else set()
                        existing_set.update(c for c in llm_cats if c != "none")
                        df.at[idx, "substance_categories"] = ", ".join(existing_set) if existing_set else "none"

    # Summary stats
    risk_counts = df["risk_severity"].value_counts()
    print(f"✅ Analysis complete. Risk distribution:")
    for level in ["critical", "high", "moderate", "low", "minimal"]:
        count = risk_counts.get(level, 0)
        if count > 0:
            print(f"   {level}: {count} posts")

    return df


def get_risk_summary(df: pd.DataFrame) -> dict:
    """Generate a summary of risk analysis results."""
    if df.empty or "risk_severity" not in df.columns:
        return {"error": "No analysis data available"}

    return {
        "total_analyzed": len(df),
        "severity_distribution": df["risk_severity"].value_counts().to_dict(),
        "substance_distribution": _count_substances(df),
        "avg_risk_score": round(df["risk_score"].mean(), 3),
        "high_risk_count": len(df[df["risk_score"] >= 0.6]),
        "signal_type_distribution": _count_signal_types(df),
        "top_keywords": _get_top_keywords(df, n=20),
    }


def _count_substances(df: pd.DataFrame) -> dict:
    """Count posts per substance category."""
    counts = {}
    for cats in df["substance_categories"]:
        if cats and cats != "none":
            for cat in cats.split(", "):
                cat = cat.strip()
                if cat:
                    counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _count_signal_types(df: pd.DataFrame) -> dict:
    """Count posts per signal type."""
    counts = {}
    for types in df["signal_types"]:
        if types and types != "none":
            for t in types.split(", "):
                t = t.strip()
                if t:
                    counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _get_top_keywords(df: pd.DataFrame, n: int = 20) -> list:
    """Get the most frequently detected keywords."""
    keyword_counts = {}
    for kws in df["keywords_matched"]:
        if kws:
            for kw in kws.split(", "):
                kw = kw.strip()
                if kw:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    sorted_kws = sorted(keyword_counts.items(), key=lambda x: -x[1])
    return [{"keyword": k, "count": v} for k, v in sorted_kws[:n]]
