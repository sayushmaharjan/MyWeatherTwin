# WeatherTwin 🌤️ + 🏥 Public Health Intelligence

**GenAI-Powered Climate & Public Health Intelligence Assistant**

WeatherTwin has expanded beyond basic forecasts to provide personalized, context-aware weather insights coupled with **Public Health Intelligence**. Our latest module focuses on **AI-Driven Substance Abuse Risk Detection from Social Media with Weather Correlation Analysis**, built for the NSF AI Challenge.

## 🎯 The Public Health Problem

Substance abuse is an urgent public health crisis. A critical challenge for public health agencies is the latency of official data (often lagging 12-18 months). Our solution leverages social media platforms (like Reddit) as **leading indicators** of community-level risk. We analyze candid discussions about substance use, recovery, and emotional crisis to extract, classify, and interpret risk signals—and correlate them with environmental conditions (weather) to surface insights through an interactive dashboard.

## 🚀 Key Features

### 🏥 Public Health Intelligence
| Feature | Description |
|---------|-------------|
| 🔍 **Risk Signal Detection** | Hybrid lexicon (rule-based) + LLM (Llama 3.3 70B via Groq) pipeline for 5-tier severity scoring. |
| 🌦️ **Weather Correlation** | Correlates linguistic risk signals with temperature, precipitation, and extreme weather flags to study Seasonal Affective Patterns. |
| 📊 **Behavioral Clusters** | Identifies clusters like Opioid Recovery, Alcohol Sobriety, and Co-occurring Distress. |
| 🧠 **Explainable AI Reasoning** | Provides LLM-generated explanations and confidence scores for every risk classification. |

### 🌍 Core Climate Intelligence
| Feature | Description |
|---------|-------------|
| 🌡️ **Current Conditions** | Real-time weather with contextual anomaly assessment. |
| 📈 **Historical & Trends** | Compare today's weather to 5-year historical norms and detect climate trends. |
| 🗓️ **Forecast & Planning** | 7-day forecast combined with AI-generated proactive climate insights. |
| 💬 **AI Chat** | Conversational Q&A about weather, public health trends, and community health insights. |

## 🏗️ Architecture & ML Methods

The public health analysis relies on a **three-layer hybrid detection pipeline**:
1. **Rule-Based Lexicon Detection:** Extracts substance (alcohol, opioids, etc.) and distress keywords using regex matching.
2. **Composite Severity Scoring:** Computes deterministic risk scores from keyword interactions.
3. **LLM-Enhanced Classification:** Blends rule-based scores with LLM reasoning (Groq API) for high precision and recall.

## 📊 Key Findings & Results

- **Risk Signal Detection:** Analyzed 691 posts, finding 23.3% at Critical severity and 29.1% High severity. The average risk score was 0.648.
- **Dominant Substances:** General substance/recovery vocabulary (589 posts), followed by Alcohol (369), Tobacco/Nicotine (169), Cannabis (124), and Benzodiazepines (20).
- **Weather Correlations:** A slight negative correlation between temperature and risk score; colder months correlated with marginally higher post frequency and distress (consistent with Seasonal Affective Patterns).
- **Temporal Patterns:** Post volume peaked during evening hours (7–10 PM), and weekend posts showed slightly higher distress.

## ⚖️ Ethical Considerations
- **No individual identification:** Anonymized authors, location inferred only at the state level.
- **Aggregate-only insights:** Built for population-level understanding, not individual intervention.
- **Transparency:** All extraction logic and uncertainties (p-values, confidence scores) are surfaced in the application.

## 🗄️ Datasets Used

| Dataset | Source | Size |
|---------|--------|------|
| **Addiction Stories** | Hugging Face (`KerenHaruvi/Addiction_Stories`) | 491 posts |
| **Reddit Mental Health Posts** | Hugging Face (`solomonk/reddit_mental_health_posts`) | ~24,000 (200 used) |
| **CDC Drug Overdose Data** | CDC Socrata Open Data API (`data.cdc.gov`) | ~500K records |
| **Historical Weather Data** | Open-Meteo Archive API | Fetched per post |

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.9+
- [Groq API Key](https://console.groq.com) (free)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Key
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_api_key_here
```

### 4. Run the Application
Our application interface operates on Streamlit.
```bash
streamlit run streamlit_app.py
```
*(If you are running the legacy FastAPI backend separately, use `cd backend && uvicorn main:app --reload --port 8000`)*

## 📚 API Endpoints (Legacy Backend Integration)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/geocode?city=...` | Resolve city name to coordinates |
| GET | `/api/weather/current?city=...` | Current weather conditions |
| GET | `/api/weather/full?city=...` | Complete weather picture + AI insight |
| POST | `/api/chat` | AI-powered contextual Q&A |

## 🔗 Data Sources
- **[Open-Meteo](https://open-meteo.com)** — Free weather API (no API key needed)
- **[Groq](https://groq.com)** — Free LLM inference for AI analysis
- **Reddit & CDC** — Public health and sentiment datasets

---

## TEAM: CLOUDMIND
- **Sayush Maharjan**
- **Harsha Sri Neeriganti**
- **[Demo Video](https://www.youtube.com/watch?v=QqnsIIVP4Ng)

