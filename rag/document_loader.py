"""
Document loader — loads CSV weather datasets and (future) wildfire PDFs.
"""

import streamlit as st
import pandas as pd

from config import DATA_DIR


@st.cache_data
def load_weather_dataset():
    """
    Load historical weather data from CSV files in the data/ directory.
    Falls back to generated sample data if files are unavailable.
    """
    try:
        df1 = pd.read_csv(DATA_DIR / "los_angeles.csv")
        df1["city"] = "Los Angeles"

        df2 = pd.read_csv(DATA_DIR / "san_diego.csv")
        df2["city"] = "San Diego"

        df3 = pd.read_csv(DATA_DIR / "san_francisco.csv")
        df3["city"] = "San Francisco"

        df = pd.concat([df1, df2, df3], ignore_index=True)

        # Create expected columns
        df["temperature"] = df["TAVG"]
        df["wind_speed"] = df["AWND"]
        df["precipitation"] = df["PRCP"]

        # Rule-based condition
        df["condition"] = df.apply(
            lambda row: "Rainy" if row["PRCP"] > 0
            else "Snowy" if row["SNOW"] > 0
            else "Clear",
            axis=1,
        )

        # Drop rows with missing temperature
        df = df.dropna(subset=["temperature"])

        return df

    except Exception as e:
        st.warning(f"⚠️ Could not load weather dataset: {e}")

        # Fallback: generate sample data
        import numpy as np

        cities = [
            "New York", "London", "Tokyo", "Paris", "Sydney", "Berlin",
            "Rome", "Madrid", "Beijing", "Moscow", "Dubai", "Singapore",
        ]
        conditions = [
            "Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Stormy",
            "Snowy", "Foggy", "Windy",
        ]

        n_records = 1000
        sample_data = {
            "city": np.random.choice(cities, n_records),
            "temperature": np.random.normal(20, 10, n_records),
            "humidity": np.random.uniform(30, 90, n_records),
            "wind_speed": np.random.uniform(5, 40, n_records),
            "pressure": np.random.normal(1013, 20, n_records),
            "condition": np.random.choice(conditions, n_records),
            "date": pd.date_range("2023-01-01", periods=n_records, freq="6H"),
        }

        df = pd.DataFrame(sample_data)
        st.info(f"ℹ️ Using sample dataset with {len(df)} records")
        return df
