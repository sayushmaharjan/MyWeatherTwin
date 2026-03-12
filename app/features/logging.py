"""
Chat logging — save and load chat history from CSV files.
"""

import os
import csv
from datetime import datetime

from config import CHAT_CSV


def save_chat_to_csv(role: str, content: str, city: str = ""):
    """Append a chat message to the CSV log file."""
    CHAT_CSV.parent.mkdir(parents=True, exist_ok=True)
    file_exists = os.path.exists(CHAT_CSV)
    with open(CHAT_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "role", "content", "city"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role,
            content,
            city,
        ])


def load_chat_from_csv():
    """Load chat history from CSV and return as a list of dicts."""
    if not os.path.exists(CHAT_CSV):
        return []
    try:
        history = []
        with open(CHAT_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "role" in row and "content" in row:
                    history.append({
                        "role": row["role"],
                        "content": row["content"],
                        "city": row.get("city", ""),
                    })
        return history
    except Exception:
        return []
