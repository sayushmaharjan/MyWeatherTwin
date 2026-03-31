# WeatherTwin 🌤️

**GenAI-Powered Climate Intelligence Assistant**

WeatherTwin goes beyond basic forecasts to provide personalized, context-aware weather insights. It uses LLMs combined with retrieval-augmented generation (RAG) to translate complex weather and climate data into clear, actionable explanations.

## Features

| Feature | Description |
|---------|-------------|
| 🌡️ **Current Conditions** | Real-time weather with contextual anomaly assessment |
| 📊 **Historical Context** | Compare today's weather to 5-year historical norms |
| 📈 **Climate Trends** | Detect warming/cooling trends with statistical analysis |
| 🗓️ **7-Day Forecast** | Hourly and daily forecast with precipitation probabilities |
| 🧠 **AI Insights** | LLM-generated proactive climate intelligence (RAG-powered) |
| 💬 **AI Chat** | Conversational Q&A about weather, trends, and planning |
| 🔄 **City Comparison** | Side-by-side comparison of two cities |
| 🗺️ **Interactive Map** | Dark-mode Leaflet map with location marker |

## Architecture

```
Frontend (HTML/CSS/JS) ←→ FastAPI Backend ←→ Open-Meteo + Groq
                                                (Weather)   (LLM)
```

## Setup

### 1. Prerequisites
- Python 3.9+
- [Groq API Key](https://console.groq.com) (free)

### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure API Key
```bash
# Create .env file in the backend/ directory
cp .env.example .env
# Edit .env and add your Groq API key
```

### 4. Run the Application
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/geocode?city=...` | Resolve city name to coordinates |
| GET | `/api/weather/current?city=...` | Current weather conditions |
| GET | `/api/weather/forecast?city=...&days=7` | Multi-day forecast |
| GET | `/api/weather/historical?city=...&years=5` | Historical climate summary |
| GET | `/api/weather/full?city=...` | Complete weather picture + AI insight |
| POST | `/api/chat` | AI-powered contextual Q&A |
| POST | `/api/compare` | Compare two cities |

## Data Sources

- **[Open-Meteo](https://open-meteo.com)** — Free weather, forecast, and historical climate APIs (no API key needed)
- **[Groq](https://groq.com)** — Free LLM inference (Llama 3.3 70B) for AI analysis

## Tech Stack

- **Frontend:** HTML5, CSS3 (custom dark-mode design), JavaScript, Chart.js, Leaflet.js
- **Backend:** Python FastAPI, httpx, OpenAI SDK (Groq-compatible)
- **AI:** Llama 3.3 70B via Groq API with RAG-based context injection
