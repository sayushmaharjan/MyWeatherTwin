"""
WeatherTwin — Entry Point
Run with: python main.py
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    app_path = os.path.join(os.path.dirname(__file__), "app", "app.py")
    sys.exit(subprocess.call(["streamlit", "run", app_path]))
