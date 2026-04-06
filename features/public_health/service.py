"""
Public Health Dashboard — data ingestion, analytics, and LLM summarization.
Uses CDC Socrata API (free, no key), SAMHSA Treatment Locator, and Groq LLM.
"""

import os
import math
import sqlite3
import requests
import pandas as pd
from datetime import datetime
from typing import Optional
from pathlib import Path

from config import sync_client as client, MODEL


# ═══════════════════════════════════════════════════
#  Database Setup
# ═══════════════════════════════════════════════════

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = str(DATA_DIR / "public_health.db")


def _get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _save_to_db(df: pd.DataFrame, table_name: str):
    conn = _get_db()
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()


# ═══════════════════════════════════════════════════
#  Data Ingestion
# ═══════════════════════════════════════════════════

def ingest_cdc_overdose_data() -> pd.DataFrame:
    """
    CDC Drug Overdose Deaths — state/county level.
    Dataset: https://data.cdc.gov/resource/xkb8-kh2a.json
    Free Socrata API — no key needed for basic use.
    """
    url = "https://data.cdc.gov/resource/xkb8-kh2a.json"
    params = {
        "$limit": 50000,
        "$order": "year DESC",
        "$where": f"year >= {datetime.now().year - 5}",
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"⚠️ CDC ingestion failed: {e}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    # Normalize columns — CDC dataset may have varying column names
    rename_map = {
        "state": "state", "state_name": "state",
        "year": "year",
        "month": "month",
        "indicator": "substance_type",
        "data_value": "death_count",
    }
    for old, new in rename_map.items():
        if old in df.columns and new != old:
            df = df.rename(columns={old: new})

    if "death_count" in df.columns:
        df["death_count"] = pd.to_numeric(df["death_count"], errors="coerce")
    df["ingested_at"] = datetime.now().isoformat()

    _save_to_db(df, "cdc_overdose")
    print(f"✅ Ingested {len(df)} CDC overdose records")
    return df


def ingest_treatment_locator() -> pd.DataFrame:
    """
    SAMHSA Treatment Facility Locator API (free, no key).
    """
    url = "https://findtreatment.samhsa.gov/locator/listing"
    params = {"pageSize": 200, "page": 1}
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data.get("rows", []))
            df["ingested_at"] = datetime.now().isoformat()
            _save_to_db(df, "treatment_facilities")
            print(f"✅ Ingested {len(df)} treatment facility records")
            return df
    except Exception as e:
        print(f"⚠️ SAMHSA ingestion failed: {e}")
    return pd.DataFrame()


def run_full_ingestion():
    """Run all ingestion jobs."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ingest_cdc_overdose_data()
    ingest_treatment_locator()
    print("✅ Full ingestion complete")


def ensure_data_loaded():
    """Check if data exists in SQLite, ingest if not."""
    try:
        conn = _get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cdc_overdose")
        count = cursor.fetchone()[0]
        conn.close()
        if count > 0:
            return True
    except Exception:
        pass
    # Data not loaded — run ingestion
    run_full_ingestion()
    return True


# ═══════════════════════════════════════════════════
#  Analytics
# ═══════════════════════════════════════════════════

def get_state_overdose_trend(state: str, substance: Optional[str] = None) -> dict:
    """Returns monthly overdose death counts for a state with spike detection."""
    try:
        ensure_data_loaded()
    except Exception:
        return {"error": f"Data not available for {state}"}

    conn = _get_db()
    query = """
        SELECT year, month, substance_type,
               AVG(death_count) as deaths
        FROM cdc_overdose
        WHERE state = ?
    """
    params = [state]
    if substance:
        query += " AND substance_type LIKE ?"
        params.append(f"%{substance}%")

    query += " GROUP BY year, month, substance_type ORDER BY year, month"

    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        conn.close()
        return {"error": f"No data found for {state}"}
    conn.close()

    if df.empty:
        return {"error": f"No data found for {state}"}

    # Rolling 3-month average for spike detection
    df["rolling_avg"] = df["deaths"].rolling(3, min_periods=1).mean()
    df["spike"] = df["deaths"] > (df["rolling_avg"] * 1.3)

    # YoY change
    latest_year = df["year"].max()
    prev_year = str(int(latest_year) - 1) if latest_year else None
    current_avg = df[df["year"] == latest_year]["deaths"].mean()
    prev_avg = df[df["year"] == prev_year]["deaths"].mean() if prev_year and prev_year in df["year"].values else None
    yoy_change_pct = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg and prev_avg > 0 else None

    return {
        "state": state,
        "substance_filter": substance,
        "total_records": len(df),
        "latest_year": str(latest_year) if latest_year else None,
        "current_year_avg_monthly": round(current_avg, 1) if not pd.isna(current_avg) else None,
        "yoy_change_pct": round(yoy_change_pct, 1) if yoy_change_pct is not None and not pd.isna(yoy_change_pct) else None,
        "spike_months": df[df["spike"] == True]["month"].tolist() if "spike" in df.columns else [],
        "trend_data": df[["year", "month", "deaths", "rolling_avg", "spike"]].to_dict("records"),
        "substances_tracked": df["substance_type"].unique().tolist() if "substance_type" in df.columns else [],
    }


def get_national_heatmap_data() -> list:
    """Aggregate overdose deaths by state for choropleth map."""
    try:
        ensure_data_loaded()
    except Exception:
        return []

    conn = _get_db()
    query = """
        SELECT state,
               SUM(death_count) as total_deaths,
               year
        FROM cdc_overdose
        WHERE year = (SELECT MAX(year) FROM cdc_overdose)
        GROUP BY state, year
        ORDER BY total_deaths DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except Exception:
        conn.close()
        return []
    conn.close()
    return df.to_dict("records")


def get_substance_breakdown(state: str) -> list:
    """What substances are driving overdoses in a given state?"""
    try:
        ensure_data_loaded()
    except Exception:
        return []

    conn = _get_db()
    query = """
        SELECT substance_type,
               SUM(death_count) as total_deaths,
               COUNT(*) as months_reported
        FROM cdc_overdose
        WHERE state = ?
          AND year = (SELECT MAX(year) FROM cdc_overdose)
        GROUP BY substance_type
        ORDER BY total_deaths DESC
        LIMIT 10
    """
    try:
        df = pd.read_sql_query(query, conn, params=[state])
    except Exception:
        conn.close()
        return []
    conn.close()
    return df.to_dict("records")


def get_nearby_treatment_facilities(lat: float, lon: float, radius_miles: float = 25) -> list:
    """Return treatment facilities within radius using Haversine distance."""
    try:
        conn = _get_db()
        df = pd.read_sql_query("SELECT * FROM treatment_facilities", conn)
        conn.close()
    except Exception:
        return []

    if df.empty or "latitude" not in df.columns:
        return []

    def haversine(lat1, lon1, lat2, lon2):
        R = 3958.8  # Earth radius in miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) *
             math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    df["distance_miles"] = df.apply(
        lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1)

    nearby = df[df["distance_miles"] <= radius_miles].sort_values("distance_miles")
    return nearby.head(10).to_dict("records")


# ═══════════════════════════════════════════════════
#  LLM Narrative Summarization
# ═══════════════════════════════════════════════════

PUBLIC_HEALTH_SYSTEM_PROMPT = """
You are a public health data analyst assistant embedded in a community
awareness dashboard. You summarize aggregated, anonymized public health
statistics to help community members, social workers, and local officials
understand substance use trends in their area.

## Your role
- Translate statistical data into clear, empathetic plain-language summaries
- Always frame findings in terms of community impact, not individual blame
- Highlight actionable resources (treatment, hotlines, prevention programs)
- Never speculate about causes beyond what the data shows
- Use person-first language (e.g., "people experiencing addiction" not "addicts")

## Hard rules
- You are summarizing AGGREGATE population statistics only
- Never make inferences about any individual person
- Always note that these are official CDC/NIDA reported figures
- End every summary with relevant support resources
- If asked about specific individuals, decline and redirect to aggregate data
"""


def generate_state_summary(state: str, substance: str = None) -> str:
    """Generate an LLM narrative summary of state overdose trends."""
    trend = get_state_overdose_trend(state, substance)
    breakdown = get_substance_breakdown(state)

    if "error" in trend:
        return f"Insufficient data available for {state}."

    breakdown_text = "\n".join([
        f"- {s['substance_type']}: {s['total_deaths']} deaths ({s['months_reported']} months reported)"
        for s in breakdown[:5]
    ]) if breakdown else "No substance breakdown available"

    context = f"""
## Overdose Trend Data — {state}
- Most recent year: {trend['latest_year']}
- Average monthly overdose deaths: {trend['current_year_avg_monthly']}
- Year-over-year change: {trend['yoy_change_pct']}% vs previous year
- Spike months detected: {trend['spike_months'] or 'None identified'}
- Substances tracked: {', '.join(trend['substances_tracked'][:5])}

## Substance Breakdown (Top causes)
{breakdown_text}

Data source: CDC Drug Overdose Surveillance System (official reported figures)
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": PUBLIC_HEALTH_SYSTEM_PROMPT},
                {"role": "user", "content": f"""
Write a 3-paragraph public health summary for {state} based on this data.

{context}

Structure:
1. Current situation — what the numbers show
2. Trend analysis — improving, worsening, or stable, and which substances
3. Community resources and what people can do

Keep it under 250 words. Plain language. Empathetic tone.
"""}
            ],
            max_tokens=400,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Summary generation failed: {e}"


def generate_trend_alert(state: str) -> dict:
    """Detects if a state has an emerging spike and generates an alert summary."""
    trend = get_state_overdose_trend(state)

    if "error" in trend:
        return {"has_alert": False}

    spike_detected = len(trend.get("spike_months", [])) > 0
    yoy_worsening = (trend.get("yoy_change_pct") or 0) > 10

    if not spike_detected and not yoy_worsening:
        return {"has_alert": False, "state": state}

    alert_context = f"""
State: {state}
Spike months: {trend['spike_months']}
YoY change: {trend['yoy_change_pct']}%
Monthly average: {trend['current_year_avg_monthly']} deaths
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": PUBLIC_HEALTH_SYSTEM_PROMPT},
                {"role": "user", "content": f"""
Write a 2-sentence public health alert (NOT alarmist, factual and constructive)
for this emerging trend. Include one specific action community members can take.

{alert_context}
"""}
            ],
            max_tokens=100,
            temperature=0.2,
        )
        alert_text = response.choices[0].message.content.strip()
    except Exception:
        alert_text = f"Emerging trend detected in {state}. Consider reaching out to local public health resources."

    return {
        "has_alert": True,
        "state": state,
        "spike_detected": spike_detected,
        "yoy_worsening": yoy_worsening,
        "alert_text": alert_text,
        "yoy_change_pct": trend.get("yoy_change_pct"),
    }


# ═══════════════════════════════════════════════════
#  Dedicated Chat — Public Health Q&A
# ═══════════════════════════════════════════════════

def answer_public_health_question(question: str, state_context: str = "") -> str:
    """
    Dedicated LLM chat for public health questions.
    Completely separate from the weather AI chat.
    """
    state_hint = f"\nThe user is currently viewing data for: {state_context}" if state_context else ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": PUBLIC_HEALTH_SYSTEM_PROMPT + state_hint},
                {"role": "user", "content": question},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"I'm unable to answer right now. Error: {e}"
