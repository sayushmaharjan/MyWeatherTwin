"""
WeatherTwin — Centralized Configuration
Loads environment variables and exposes project-wide constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
USERS_FILE = BASE_DIR / "auth" / "users.csv"
CHAT_LOG_DIR = BASE_DIR / "logs" / "chat"
EVENT_LOG_DIR = BASE_DIR / "logs" / "events"
LOG_FILE = EVENT_LOG_DIR / "query_log.csv"
CHAT_CSV = CHAT_LOG_DIR / "chat_log.csv"
REPORTS_DIR = BASE_DIR / "reports"

# Ensure log directories exist
CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)
EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Environment ────────────────────────────────────────
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHERAPI_KEY = os.getenv("WEATHERAPI_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# ── LLM ────────────────────────────────────────────────
MODEL = "llama-3.3-70b-versatile"

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# ── Dev Mode ───────────────────────────────────────────
DEV_MODE = True
