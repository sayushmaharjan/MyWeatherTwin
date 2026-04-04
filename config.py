import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "backend" / ".env", override=True)

WEATHERAPI_KEY = os.getenv("WEATHERAPI_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# We import the LLM client directly from the existing backend llm_service 
# so the agent folder doesn't break, and they share the same Groq instantiation.
from backend.llm_service import client

MODEL = "llama-3.3-70b-versatile"
MODEL_SMALL = "llama-3.1-8b-instant" # llama-3.1-8b-instant OR mixtral-8x7b

LOG_FILE = Path(__file__).parent / "backend" / "agent_logs.txt"
