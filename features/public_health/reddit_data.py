"""
Reddit Data Ingestion — loads Hugging Face addiction/mental health datasets,
normalizes them into a unified schema, and stores them in SQLite.
Sources:
  - KerenHaruvi/Addiction_Stories (491 posts)
  - solomonk/reddit_mental_health_posts (substance-filtered subset)
"""

import os
import random
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = str(DATA_DIR / "public_health.db")

# US states for simulated location assignment
US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY",
]

# Higher-population states weighted more heavily
STATE_WEIGHTS = {
    "CA": 5, "TX": 4, "FL": 4, "NY": 4, "PA": 3, "IL": 3, "OH": 3,
    "GA": 2, "NC": 2, "MI": 2, "NJ": 2, "VA": 2, "WA": 2, "AZ": 2,
    "MA": 2, "TN": 2, "IN": 2, "MO": 2, "MD": 2, "WI": 2, "CO": 2,
    "MN": 2, "SC": 2, "AL": 2, "LA": 2, "KY": 2, "OR": 2, "OK": 2,
    "CT": 1, "UT": 1, "IA": 1, "NV": 1, "AR": 1, "MS": 1, "KS": 1,
    "NM": 1, "NE": 1, "ID": 1, "WV": 2, "HI": 1, "NH": 1, "ME": 1,
    "RI": 1, "MT": 1, "DE": 1, "SD": 1, "ND": 1, "AK": 1, "VT": 1,
    "WY": 1,
}

# State coordinates (approximate centroids) for weather data fetching
STATE_COORDS = {
    "AL": (32.8, -86.8), "AK": (64.0, -153.0), "AZ": (34.3, -111.7),
    "AR": (34.8, -92.2), "CA": (37.2, -119.5), "CO": (39.0, -105.5),
    "CT": (41.6, -72.7), "DE": (39.0, -75.5), "FL": (28.6, -82.4),
    "GA": (32.7, -83.4), "HI": (20.5, -157.4), "ID": (44.4, -114.6),
    "IL": (40.0, -89.2), "IN": (39.9, -86.3), "IA": (42.0, -93.5),
    "KS": (38.5, -98.3), "KY": (37.8, -85.3), "LA": (31.0, -92.0),
    "ME": (45.4, -69.2), "MD": (39.0, -76.7), "MA": (42.3, -71.8),
    "MI": (44.3, -84.6), "MN": (46.3, -94.3), "MS": (32.7, -89.7),
    "MO": (38.4, -92.5), "MT": (47.1, -109.6), "NE": (41.5, -99.8),
    "NV": (39.4, -116.7), "NH": (43.7, -71.6), "NJ": (40.1, -74.7),
    "NM": (34.4, -106.1), "NY": (42.2, -74.9), "NC": (35.6, -79.4),
    "ND": (47.5, -100.5), "OH": (40.4, -82.8), "OK": (35.6, -97.5),
    "OR": (44.1, -120.5), "PA": (40.9, -77.8), "RI": (41.7, -71.5),
    "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.9, -86.4),
    "TX": (31.5, -99.3), "UT": (39.3, -111.7), "VT": (44.1, -72.6),
    "VA": (37.5, -78.9), "WA": (47.4, -120.7), "WV": (38.6, -80.6),
    "WI": (44.6, -89.7), "WY": (43.0, -107.6),
}


def _get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _weighted_random_state() -> str:
    """Pick a random US state weighted by population."""
    states = list(STATE_WEIGHTS.keys())
    weights = list(STATE_WEIGHTS.values())
    return random.choices(states, weights=weights, k=1)[0]


def _generate_timestamps(n: int, months_back: int = 12) -> list:
    """Generate realistic timestamps spread over the past N months with seasonal variation."""
    now = datetime.utcnow()
    timestamps = []
    for _ in range(n):
        # Random date within the past N months
        days_back = random.randint(0, months_back * 30)
        dt = now - timedelta(days=days_back)
        # Add random time of day (weighted toward evening/night hours)
        hour = random.choices(
            range(24),
            weights=[1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 5, 5, 5, 5, 6, 7, 8, 9, 10, 10, 9, 7, 4, 2],
            k=1
        )[0]
        minute = random.randint(0, 59)
        dt = dt.replace(hour=hour, minute=minute, second=random.randint(0, 59))
        timestamps.append(dt.timestamp())
    return timestamps


def load_addiction_stories() -> pd.DataFrame:
    """Load the KerenHaruvi/Addiction_Stories dataset from local CSV."""
    csv_path = DATA_DIR / "addiction_stories.csv"
    if not csv_path.exists():
        print("⚠️ addiction_stories.csv not found. Run download script first.")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    n = len(df)
    timestamps = _generate_timestamps(n, months_back=12)

    # Normalize to unified schema
    records = []
    for idx, row in df.iterrows():
        state = _weighted_random_state()
        records.append({
            "post_id": f"addiction_{row.get('example_id', idx)}",
            "subreddit": random.choice([
                "r/addiction", "r/stopdrinking", "r/opiatesrecovery",
                "r/leaves", "r/REDDITORSINRECOVERY", "r/cripplingalcoholism",
            ]),
            "title": "",  # Addiction stories don't have separate titles
            "body": str(row.get("text", "")),
            "author": f"anon_{random.randint(10000, 99999)}",
            "created_utc": timestamps[idx],
            "score": random.randint(1, 500),
            "num_comments": random.randint(0, 80),
            "label": str(row.get("label", "")),
            "source_dataset": "KerenHaruvi/Addiction_Stories",
            "location_state": state,
        })

    return pd.DataFrame(records)


def load_depression_substance_posts() -> pd.DataFrame:
    """Load substance-filtered depression posts from local CSV."""
    csv_path = DATA_DIR / "reddit_depression_substance.csv"
    if not csv_path.exists():
        print("⚠️ reddit_depression_substance.csv not found.")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    n = len(df)
    timestamps = _generate_timestamps(n, months_back=12)

    records = []
    for idx, row in df.iterrows():
        state = _weighted_random_state()
        records.append({
            "post_id": f"depression_{row.get('id', idx)}",
            "subreddit": f"r/{row.get('subreddit', 'depression')}",
            "title": str(row.get("title", "")),
            "body": str(row.get("body", "")),
            "author": f"anon_{random.randint(10000, 99999)}",
            "created_utc": timestamps[idx],
            "score": int(row.get("score", 1)) if pd.notna(row.get("score")) else 1,
            "num_comments": int(row.get("num_comments", 0)) if pd.notna(row.get("num_comments")) else 0,
            "label": "depression_comorbid",
            "source_dataset": "solomonk/reddit_mental_health_posts",
            "location_state": state,
        })

    return pd.DataFrame(records)


def ingest_reddit_data() -> pd.DataFrame:
    """Load all Reddit datasets, merge, and store in SQLite."""
    print("📡 Loading Reddit substance abuse datasets...")

    df_addiction = load_addiction_stories()
    df_depression = load_depression_substance_posts()

    parts = [df for df in [df_addiction, df_depression] if not df.empty]
    if not parts:
        print("⚠️ No Reddit data available.")
        return pd.DataFrame()

    df_all = pd.concat(parts, ignore_index=True)
    df_all["ingested_at"] = datetime.now().isoformat()

    # Save to SQLite
    conn = _get_db()
    df_all.to_sql("reddit_posts", conn, if_exists="replace", index=False)
    conn.close()

    print(f"✅ Ingested {len(df_all)} Reddit posts ({len(df_addiction)} addiction + {len(df_depression)} depression/substance)")
    return df_all


def get_reddit_posts() -> pd.DataFrame:
    """Retrieve all Reddit posts from SQLite."""
    try:
        conn = _get_db()
        df = pd.read_sql_query("SELECT * FROM reddit_posts", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def ensure_reddit_data() -> bool:
    """Check if Reddit data exists in SQLite, ingest if not."""
    try:
        conn = _get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reddit_posts")
        count = cursor.fetchone()[0]
        conn.close()
        if count > 0:
            return True
    except Exception:
        pass
    ingest_reddit_data()
    return True


def get_dataset_summary() -> dict:
    """Return a summary of the loaded Reddit datasets."""
    df = get_reddit_posts()
    if df.empty:
        return {"total_posts": 0}

    return {
        "total_posts": len(df),
        "datasets": df["source_dataset"].value_counts().to_dict(),
        "subreddits": df["subreddit"].value_counts().to_dict(),
        "labels": df["label"].value_counts().to_dict(),
        "states_covered": df["location_state"].nunique(),
        "date_range": {
            "earliest": datetime.fromtimestamp(df["created_utc"].min()).strftime("%Y-%m-%d") if df["created_utc"].notna().any() else "N/A",
            "latest": datetime.fromtimestamp(df["created_utc"].max()).strftime("%Y-%m-%d") if df["created_utc"].notna().any() else "N/A",
        },
    }


def get_state_coords(state: str) -> tuple:
    """Get approximate lat/lon for a US state."""
    return STATE_COORDS.get(state, (39.8, -98.6))  # Default: geographic center of US
