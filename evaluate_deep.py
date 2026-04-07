"""
WeatherTwin LLM Evaluation Suite
=================================
Evaluates llama-3.3-70b-versatile against baseline models on Groq.
Uses DeepSeek API as the LLM judge (free tier).
Parses real logs, runs multi-model comparison, scores with LLM-as-judge,
and saves results to eval_results.json for the dashboard.

Usage:
    python evaluate.py --groq-key GK --deepseek-key DSK
    python evaluate.py --skip-live                      # log analysis only
    python evaluate.py --groq-key GK --deepseek-key DSK --delay 3.0
"""

import argparse
import json
import os
import re
import time
import statistics
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "backend" / ".env", override=True)

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️  groq package not found. Run: pip install groq")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  openai package not found. Run: pip install openai")


# ─── Provider constants ───────────────────────────────────────────────────────
PROVIDER_GROQ   = "groq"
PROVIDER_DEEPSEEK = "deepseek"

# ─── Model registry ───────────────────────────────────────────────────────────
# All models run on Groq. Set enabled=False to skip any model.
MODELS = {
    "llama-3.3-70b-versatile": {
        "provider": PROVIDER_GROQ,
        "label":    "LLaMA 3.3 70B (Primary)",
        "color":    "#3b82f6",
        "tier":     "primary",
        "enabled":  True,
    },
    "llama-3.1-8b-instant": {
        "provider": PROVIDER_GROQ,
        "label":    "LLaMA 3.1 8B Instant (Groq-Fast)",
        "color":    "#8b5cf6",
        "tier":     "groq-fast",
        "enabled":  True,
    },
    "openai/gpt-oss-120b": {
        "provider": PROVIDER_GROQ,
        "label":    "GPT-OSS 120B (via Groq)",
        "color":    "#10b981",
        "tier":     "openai-groq",
        "enabled":  True,
    },
    "openai/gpt-oss-20b": {
        "provider": PROVIDER_GROQ,
        "label":    "GPT-OSS 20B (via Groq)",
        "color":    "#f59e0b",
        "tier":     "openai-groq",
        "enabled":  True,
    },
}

# Judge model — DeepSeek (free tier) via OpenAI-compatible API
JUDGE_MODEL    = "deepseek-reasoner"   # DeepSeek-V3, free tier
JUDGE_PROVIDER = PROVIDER_DEEPSEEK


# ─── Test scenarios (real weather data from your logs) ───────────────────────
TEST_SCENARIOS = [
    {
        "id": "kc_clear_warm",
        "city": "Kansas City",
        "lat": 39.09973,
        "lon": -94.57857,
        "country": "United States",
        "current": {
            "temperature": 18.23,
            "condition": "Mainly clear",
            "humidity": 55,
            "wind_speed": 14,
            "precipitation": 0.0,
            "feels_like": 17.1,
        },
        "forecast_summary": "Mild temperatures 15-20°C, mostly clear skies for 3 days, chance of rain Thursday",
        "historical_avg_temp": 14.5,
        "historical_comparison": "4°C above seasonal average",
        "user_question": "What should I know about today's weather in Kansas City?",
        "tags": ["above_avg_temp", "clear", "midwest"],
    },
    {
        "id": "kc_overcast_cool",
        "city": "Kansas City",
        "lat": 39.09973,
        "lon": -94.57857,
        "country": "United States",
        "current": {
            "temperature": 10.21,
            "condition": "Overcast",
            "humidity": 72,
            "wind_speed": 20,
            "precipitation": 0.2,
            "feels_like": 8.0,
        },
        "forecast_summary": "Overcast and cool all week, possible thunderstorms Friday, lows near 5°C",
        "historical_avg_temp": 14.5,
        "historical_comparison": "4°C below seasonal average — unusually cold",
        "user_question": "Is it going to rain this week in Kansas City? Should I bring an umbrella?",
        "tags": ["below_avg_temp", "overcast", "rain_risk"],
    },
    {
        "id": "bengaluru_clear",
        "city": "Bengaluru",
        "lat": 12.97194,
        "lon": 77.59369,
        "country": "India",
        "current": {
            "temperature": 23.17,
            "condition": "Clear sky",
            "humidity": 48,
            "wind_speed": 8,
            "precipitation": 0.0,
            "feels_like": 22.5,
        },
        "forecast_summary": "Warm and clear 22-27°C, pre-monsoon humidity building mid-week",
        "historical_avg_temp": 24.0,
        "historical_comparison": "Near seasonal average — typical April conditions",
        "user_question": "How is the weather in Bengaluru today? Is the monsoon coming?",
        "tags": ["tropical", "clear", "pre_monsoon"],
    },
    {
        "id": "bengaluru_overcast",
        "city": "Bengaluru",
        "lat": 12.97194,
        "lon": 77.59369,
        "country": "India",
        "current": {
            "temperature": 23.36,
            "condition": "Overcast",
            "humidity": 68,
            "wind_speed": 12,
            "precipitation": 0.4,
            "feels_like": 24.1,
        },
        "forecast_summary": "Overcast with intermittent showers, humidity 65-75%, cooler evenings",
        "historical_avg_temp": 24.0,
        "historical_comparison": "Slightly below average — early pre-monsoon cloudiness",
        "user_question": "Should I carry an umbrella in Bengaluru today?",
        "tags": ["tropical", "overcast", "light_rain"],
    },
    {
        "id": "nyc_cold_overcast",
        "city": "New York",
        "lat": 40.71427,
        "lon": -74.00597,
        "country": "United States",
        "current": {
            "temperature": 6.72,
            "condition": "Overcast",
            "humidity": 80,
            "wind_speed": 25,
            "precipitation": 0.1,
            "feels_like": 3.2,
        },
        "forecast_summary": "Cold and overcast, feels like near freezing, possible light snow Thursday",
        "historical_avg_temp": 10.0,
        "historical_comparison": "3°C below seasonal average — cold snap in effect",
        "user_question": "It feels really cold in New York. Is this normal for this time of year?",
        "tags": ["cold_snap", "overcast", "northeast"],
    },
    {
        "id": "nyc_mild_clear",
        "city": "New York",
        "lat": 40.71427,
        "lon": -74.00597,
        "country": "United States",
        "current": {
            "temperature": 15.2,
            "condition": "Clear sky",
            "humidity": 52,
            "wind_speed": 15,
            "precipitation": 0.0,
            "feels_like": 14.8,
        },
        "forecast_summary": "Pleasant and sunny 13-17°C all week, ideal outdoor conditions",
        "historical_avg_temp": 10.0,
        "historical_comparison": "5°C above seasonal average — exceptionally mild",
        "user_question": "Is this a good week for outdoor activities in New York?",
        "tags": ["above_avg_temp", "clear", "pleasant"],
    },
    {
        "id": "london_overcast",
        "city": "City of Westminster",
        "lat": 51.50853,
        "lon": -0.12574,
        "country": "United Kingdom",
        "current": {
            "temperature": 9.5,
            "condition": "Overcast",
            "humidity": 83,
            "wind_speed": 18,
            "precipitation": 0.6,
            "feels_like": 6.9,
        },
        "forecast_summary": "Typical London grey, overcast with drizzle, 8-11°C, some sun patches Friday",
        "historical_avg_temp": 10.5,
        "historical_comparison": "Slightly below average — persistent overcast blocking warmth",
        "user_question": "What's the weather like in London this week? Is it worth going out?",
        "tags": ["overcast", "drizzle", "europe"],
    },
    {
        "id": "edge_extreme_heat",
        "city": "Kansas City",
        "lat": 39.09973,
        "lon": -94.57857,
        "country": "United States",
        "current": {
            "temperature": 38.5,
            "condition": "Sunny",
            "humidity": 30,
            "wind_speed": 5,
            "precipitation": 0.0,
            "feels_like": 40.2,
        },
        "forecast_summary": "Heat dome persisting all week, 36-40°C, heat index above 42°C, no relief until Sunday",
        "historical_avg_temp": 28.0,
        "historical_comparison": "10°C above seasonal average — dangerous heat wave",
        "user_question": "Is it safe to go for a run outside today in Kansas City?",
        "tags": ["extreme_heat", "safety_critical", "edge_case"],
    },
    {
        "id": "edge_missing_data",
        "city": "Kansas City",
        "lat": 39.09973,
        "lon": -94.57857,
        "country": "United States",
        "current": {
            "temperature": None,
            "condition": "Unknown",
            "humidity": None,
            "wind_speed": None,
            "precipitation": None,
            "feels_like": None,
        },
        "forecast_summary": "Data unavailable",
        "historical_avg_temp": 14.5,
        "historical_comparison": "N/A",
        "user_question": "What's the weather like today?",
        "tags": ["edge_case", "missing_data", "graceful_degradation"],
    },
]

SYSTEM_PROMPT = """You are WeatherTwin, an AI Climate Intelligence Assistant.
You provide friendly, accurate, and actionable weather insights.
Keep responses to 2-3 concise paragraphs. Do not use markdown headers.
Always mention if conditions are unusual compared to historical averages.
Prioritize safety if conditions are dangerous."""


def build_user_prompt(scenario: dict) -> str:
    """Construct the weather insight prompt from a scenario."""
    c = scenario["current"]

    def fmt(val, unit=""):
        return f"{val}{unit}" if val is not None else "N/A"

    return f"""Generate a proactive weather insight for {scenario['city']}, {scenario['country']}.

Current Conditions:
- Temperature: {fmt(c['temperature'], '°C')} (feels like {fmt(c['feels_like'], '°C')})
- Condition: {c['condition']}
- Humidity: {fmt(c['humidity'], '%')}
- Wind Speed: {fmt(c['wind_speed'], ' km/h')}
- Precipitation: {fmt(c['precipitation'], 'mm')}

7-Day Forecast Summary: {scenario['forecast_summary']}
Historical Context: {scenario['historical_comparison']} (avg {scenario['historical_avg_temp']}°C)

User Question: {scenario['user_question']}

Provide a helpful, friendly insight. Plain text paragraphs only, no headers."""


JUDGE_PROMPT_TEMPLATE = """You are an expert evaluator for a weather AI assistant.
Score the following response on 5 criteria, each from 1 to 5.

WEATHER CONTEXT:
City: {city}
Condition: {condition}, {temperature}°C
Historical: {historical_comparison}

USER QUESTION: {user_question}

AI RESPONSE TO EVALUATE:
{response}

SCORING RUBRIC:
1. accuracy (1-5): Does the response correctly reflect the weather data provided?
   5=perfectly accurate, 3=minor errors, 1=hallucinated facts
2. helpfulness (1-5): Does it give actionable, useful advice for the user's question?
   5=highly actionable, 3=somewhat useful, 1=vague or useless
3. tone (1-5): Is it friendly, appropriately confident, not robotic?
   5=warm and natural, 3=neutral/ok, 1=robotic or overly formal
4. conciseness (1-5): Is it appropriately concise (2-3 paragraphs, no fluff)?
   5=perfect length, 3=slightly long/short, 1=way too long or too short
5. instruction_following (1-5): Did it avoid markdown headers, stay in plain text paragraphs?
   5=followed all instructions, 3=minor deviation, 1=ignored instructions

Respond ONLY with valid JSON, no explanation, no markdown:
{{"accuracy": <int>, "helpfulness": <int>, "tone": <int>, "conciseness": <int>, "instruction_following": <int>, "reasoning": "<10 words max>"}}"""


# ─── Log Parsers ──────────────────────────────────────────────────────────────

def parse_app_logs(path: str) -> dict:
    """Parse app.jsonl for latency stats."""
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        abs_path = os.path.abspath(path)
        print(f"⚠️  Log file not found: {abs_path}")
        print(f"   Pass the full path: --app-log /full/path/to/app.jsonl")
        return {}

    city_latencies = {}
    coord_latencies = []
    all_latencies = []

    for r in records:
        lat = r.get("latency_ms")
        if lat is None:
            continue
        all_latencies.append(lat)
        if r.get("function") == "fetch_weather_by_city":
            city = r.get("city", "unknown").lower()
            city_latencies.setdefault(city, []).append(lat)
        elif r.get("function") == "fetch_weather_by_coords":
            coord_latencies.append(lat)

    return {
        "total_fetches": len(records),
        "all_latencies_ms": all_latencies,
        "avg_latency_ms": round(statistics.mean(all_latencies), 1) if all_latencies else 0,
        "median_latency_ms": round(statistics.median(all_latencies), 1) if all_latencies else 0,
        "p95_latency_ms": round(sorted(all_latencies)[int(len(all_latencies) * 0.95)], 1) if all_latencies else 0,
        "min_latency_ms": round(min(all_latencies), 1) if all_latencies else 0,
        "max_latency_ms": round(max(all_latencies), 1) if all_latencies else 0,
        "city_latencies": {
            city: {"avg_ms": round(statistics.mean(lats), 1), "count": len(lats)}
            for city, lats in city_latencies.items()
        },
        "coord_fetches": len(coord_latencies),
        "coord_avg_ms": round(statistics.mean(coord_latencies), 1) if coord_latencies else 0,
    }


def parse_llm_logs(path: str) -> dict:
    """Parse llm_service.jsonl for token usage, latency, errors."""
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        abs_path = os.path.abspath(path)
        print(f"⚠️  Log file not found: {abs_path}")
        print(f"   Pass the full path: --llm-log /full/path/to/llm_service.jsonl")
        return {}

    successes = [r for r in records if r.get("level") == "INFO" and r.get("tokens")]
    errors    = [r for r in records if r.get("level") == "ERROR"]
    rate_limit_errors = [r for r in errors if "rate_limit_exceeded" in r.get("message", "")]

    # Pair "Generating" requests with "Insight generated" responses to attach city names
    request_records = [r for r in records if "Generating proactive insight for" in r.get("message", "")]
    for req in request_records:
        city   = req.get("city", "")
        req_ts = req.get("timestamp", "")
        for s in successes:
            if not s.get("city") and s.get("timestamp", "") > req_ts:
                s["city"] = city
                break

    latencies = [r["latency_ms"] for r in successes if r.get("latency_ms")]
    tokens    = [r["tokens"]     for r in successes if r.get("tokens")]

    tpd_usages = []
    for r in rate_limit_errors:
        m = re.search(r"Used (\d+), Requested (\d+)", r.get("message", ""))
        if m:
            tpd_usages.append({"used": int(m.group(1)), "requested": int(m.group(2))})

    city_stats = {}
    for r in successes:
        city = r.get("city", "unknown")
        city_stats.setdefault(city, {"count": 0, "total_tokens": 0, "latencies": []})
        city_stats[city]["count"] += 1
        city_stats[city]["total_tokens"] += r.get("tokens", 0)
        if r.get("latency_ms"):
            city_stats[city]["latencies"].append(r["latency_ms"])

    city_summary = {
        city: {
            "calls": s["count"],
            "avg_tokens": round(s["total_tokens"] / s["count"]) if s["count"] else 0,
            "avg_latency_ms": round(statistics.mean(s["latencies"]), 1) if s["latencies"] else 0,
        }
        for city, s in city_stats.items()
    }

    total_tokens_used    = sum(tokens)
    tpd_limit            = 100000
    tpd_utilization_pct  = round((total_tokens_used / tpd_limit) * 100, 1)

    return {
        "total_calls": len([r for r in records
                            if r.get("function") == "generate_proactive_insight"
                            and "Generating" in r.get("message", "")]),
        "successful_calls":    len(successes),
        "failed_calls":        len(errors),
        "rate_limit_errors":   len(rate_limit_errors),
        "success_rate_pct":    round(len(successes) / max(len(successes) + len(errors), 1) * 100, 1),
        "avg_latency_ms":      round(statistics.mean(latencies), 1) if latencies else 0,
        "median_latency_ms":   round(statistics.median(latencies), 1) if latencies else 0,
        "p95_latency_ms":      round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if len(latencies) >= 2 else 0,
        "avg_tokens":          round(statistics.mean(tokens), 1) if tokens else 0,
        "min_tokens":          min(tokens) if tokens else 0,
        "max_tokens":          max(tokens) if tokens else 0,
        "total_tokens_logged": total_tokens_used,
        "tpd_limit":           tpd_limit,
        "tpd_utilization_pct": tpd_utilization_pct,
        "tpd_peak_usages":     tpd_usages[:5],
        "city_stats":          city_summary,
        "model":               "llama-3.3-70b-versatile",
    }


def parse_weather_logs(path: str) -> dict:
    """Parse weather_service.jsonl for service call patterns."""
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        abs_path = os.path.abspath(path)
        print(f"⚠️  Log file not found: {abs_path}")
        print(f"   Pass the full path: --weather-log /full/path/to/weather_service.jsonl")
        return {}

    service_counts = {}
    city_weather   = {}

    for r in records:
        service = r.get("service", "unknown")
        service_counts[service] = service_counts.get(service, 0) + 1

        if r.get("function") == "get_current_weather" and "Current weather:" in r.get("message", ""):
            city = r.get("city")
            m    = re.search(r"([\d.]+)°C, (.+)$", r["message"])
            if m and city:
                city_weather.setdefault(city, []).append({
                    "temp_c":    float(m.group(1)),
                    "condition": m.group(2).strip(),
                    "timestamp": r.get("timestamp"),
                })

    return {
        "total_log_entries": len(records),
        "service_call_counts": service_counts,
        "unique_cities": list(city_weather.keys()),
        "city_weather_readings": {
            city: {
                "reading_count": len(readings),
                "temps_c":       [r["temp_c"] for r in readings],
                "conditions":    list(set(r["condition"] for r in readings)),
                "avg_temp_c":    round(statistics.mean(r["temp_c"] for r in readings), 2),
            }
            for city, readings in city_weather.items()
        },
        "historical_fetch_count": len([
            r for r in records
            if r.get("function") == "get_historical_summary" and "Fetching" in r.get("message", "")
        ]),
        "geocoding_calls": service_counts.get("OpenMeteo", 0) + service_counts.get("Nominatim", 0),
    }


# ─── Client factory ───────────────────────────────────────────────────────────

def _make_clients(groq_key: str = "", deepseek_key: str = "") -> dict:
    """Build provider -> client dict. Only creates clients for keys provided."""
    clients = {}
    if groq_key:
        if not GROQ_AVAILABLE:
            print("⚠️  groq package missing. Run: pip install groq")
        else:
            clients[PROVIDER_GROQ] = Groq(api_key=groq_key)
    if deepseek_key:
        if not OPENAI_AVAILABLE:
            print("⚠️  openai package missing. Run: pip install openai")
        else:
            # DeepSeek uses OpenAI-compatible endpoint
            clients[PROVIDER_DEEPSEEK] = OpenAI(
                api_key=deepseek_key,
                base_url="https://api.deepseek.com/v1"
            )
    return clients


# ─── Model caller ─────────────────────────────────────────────────────────────

def call_model(groq_client, model_id: str, scenario: dict, max_tokens: int = 512) -> dict:
    """Call a Groq-hosted model. All models in MODELS use Groq."""
    prompt = build_user_prompt(scenario)
    start  = time.perf_counter()
    try:
        response   = groq_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        text       = response.choices[0].message.content
        usage      = response.usage
        return {
            "success":           True,
            "response":          text,
            "latency_ms":        round(elapsed_ms, 1),
            "prompt_tokens":     usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens":      usage.total_tokens,
            "error":             None,
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "success":           False,
            "response":          "",
            "latency_ms":        round(elapsed_ms, 1),
            "prompt_tokens":     0,
            "completion_tokens": 0,
            "total_tokens":      0,
            "error":             str(e),
        }


# ─── Judge (DeepSeek) ─────────────────────────────────────────────────────────

def _extract_json_from_text(text: str) -> dict:
    """
    Aggressively extract a JSON object from LLM output.
    Handles: plain JSON, ```json fences, JSON buried in prose, trailing commas.
    """
    text = re.sub(r"```json\s*|```\s*", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        candidate = re.sub(r",\s*([}\]])", r"\1", match.group(0))
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Field-by-field regex fallback
    scores = {}
    for field in ["accuracy", "helpfulness", "tone", "conciseness", "instruction_following"]:
        m = re.search(rf'"{field}"\s*:\s*(\d)', text)
        if m:
            scores[field] = int(m.group(1))
    m = re.search(r'"reasoning"\s*:\s*"([^"]+)"', text)
    if m:
        scores["reasoning"] = m.group(1)
    if scores:
        return scores

    raise ValueError(f"Could not extract JSON from judge output: {text[:200]}")


def judge_response(deepseek_client, scenario: dict, response_text: str,
                   debug: bool = False) -> dict:
    """
    Score a model response using DeepSeek as judge.
    Returns score dict with composite weighted score.
    """
    ZERO_SCORES = {
        "accuracy": 0, "helpfulness": 0, "tone": 0,
        "conciseness": 0, "instruction_following": 0,
        "composite": 0.0,
    }

    if not response_text or not response_text.strip():
        return {**ZERO_SCORES, "reasoning": "Empty response — not scored"}

    c = scenario["current"]
    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
        city=scenario["city"],
        condition=c.get("condition", "N/A"),
        temperature=c.get("temperature", "N/A"),
        historical_comparison=scenario["historical_comparison"],
        user_question=scenario["user_question"],
        response=response_text,
    )

    raw = ""
    try:
        # DeepSeep expects OpenAI chat format
        completion = deepseek_client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": "You are a strict JSON evaluator. Respond only with valid JSON."},
                {"role": "user", "content": judge_prompt + "\n\nIMPORTANT: Respond with a single valid JSON object only. No markdown, no prose. Example format: {\"accuracy\": 4, \"helpfulness\": 4, \"tone\": 4, \"conciseness\": 4, \"instruction_following\": 4, \"reasoning\": \"Brief reason.\"}"}
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        raw = completion.choices[0].message.content.strip()

        if debug:
            print(f"\n    [judge raw] {raw[:300]}")

        scores = _extract_json_from_text(raw)
        required = ["accuracy", "helpfulness", "tone", "conciseness", "instruction_following"]
        for key in required:
            val = scores.get(key)
            if val is None:
                raise ValueError(f"Missing judge score key: '{key}'")
            scores[key] = max(1, min(5, int(val)))

        weights = {
            "accuracy": 0.30, "helpfulness": 0.30, "tone": 0.15,
            "conciseness": 0.10, "instruction_following": 0.15,
        }
        scores["composite"] = round(sum(scores[k] * w for k, w in weights.items()), 3)
        scores["judge_model"] = JUDGE_MODEL
        scores["judge_provider"] = JUDGE_PROVIDER
        return scores

    except Exception as e:
        reason = f"Judge parse error: {e} | raw='{raw[:120]}'" if raw else f"Judge API error: {e}"
        print(f"\n    ⚠️  {reason}")
        return {**ZERO_SCORES, "reasoning": reason,
                "judge_model": JUDGE_MODEL, "judge_provider": JUDGE_PROVIDER}


# ─── Main Evaluation Runner ───────────────────────────────────────────────────

def run_evaluation(groq_key: str, deepseek_key: str,
                   output_path: str = "eval_results.json",
                   rate_limit_delay: float = 2.0) -> dict:
    """
    Run full evaluation: call every enabled model on every scenario,
    score each response with DeepSeek judge, save results.
    rate_limit_delay: seconds between Groq calls to respect 100K TPD free tier.
    """
    clients = _make_clients(groq_key=groq_key, deepseek_key=deepseek_key)

    groq_client   = clients.get(PROVIDER_GROQ)
    deepseek_client = clients.get(PROVIDER_DEEPSEEK)

    if not groq_client:
        print("❌ Groq client not available. Check --groq-key.")
        return {}
    if not deepseek_client:
        print("❌ DeepSeek client not available. Check --deepseek-key.")
        return {}

    active_models = {mid: cfg for mid, cfg in MODELS.items() if cfg.get("enabled", True)}

    results = {
        "meta": {
            "run_timestamp":    datetime.utcnow().isoformat() + "Z",
            "primary_model":    "llama-3.3-70b-versatile",
            "judge_model":      JUDGE_MODEL,
            "judge_provider":   JUDGE_PROVIDER,
            "models_evaluated": list(active_models.keys()),
            "scenarios_count":  len(TEST_SCENARIOS),
            "rate_limit_delay_s": rate_limit_delay,
        },
        "model_results":    {mid: [] for mid in active_models},
        "scenario_results": {},
        "model_summary":    {},
    }

    total_calls = len(active_models) * len(TEST_SCENARIOS)
    call_num    = 0

    print(f"\n{'='*60}")
    print(f"WeatherTwin LLM Evaluation")
    print(f"⚖️  Judge: {JUDGE_MODEL} (DeepSeek)")
    print(f"Models: {len(active_models)} | Scenarios: {len(TEST_SCENARIOS)} | Total calls: {total_calls}")
    print(f"{'='*60}\n")

    for scenario in TEST_SCENARIOS:
        sid = scenario["id"]
        print(f"\n📍 Scenario: {scenario['city']} — {sid}")
        print(f"   Question: {scenario['user_question'][:60]}...")
        results["scenario_results"][sid] = {"scenario": scenario, "model_outputs": {}}

        for model_id, cfg in active_models.items():
            call_num += 1
            print(f"   [{call_num}/{total_calls}] {cfg['label']}... ", end="", flush=True)

            output = call_model(groq_client, model_id, scenario)
            time.sleep(rate_limit_delay)          # Groq rate limit buffer

            if not output["success"]:
                print(f"❌ ERROR: {output['error'][:80]}")
            else:
                print(f"✅ {output['latency_ms']:.0f}ms | {output['total_tokens']} tokens"
                      " | judging...", end="", flush=True)
                scores = judge_response(deepseek_client, scenario, output["response"])
                output["scores"] = scores
                time.sleep(0.3)                   # small polite delay for DeepSeek
                print(f" score={scores.get('composite', 0):.2f}")

            results["model_results"][model_id].append({
                "scenario_id":   sid,
                "scenario_city": scenario["city"],
                "scenario_tags": scenario["tags"],
                **output,
            })
            results["scenario_results"][sid]["model_outputs"][model_id] = output

    # ── Summary stats ─────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("Computing summary statistics...\n")

    for model_id, runs in results["model_results"].items():
        successful = [r for r in runs if r.get("success")]
        scored     = [r for r in successful if r.get("scores")]

        def safe_mean(lst):
            return round(statistics.mean(lst), 2) if lst else 0

        def avg_score(key):
            return safe_mean([r["scores"].get(key, 0) for r in scored])

        latencies = [r["latency_ms"]   for r in successful]
        tokens    = [r["total_tokens"] for r in successful]

        summary = {
            "model_id":                model_id,
            "label":                   MODELS[model_id]["label"],
            "color":                   MODELS[model_id]["color"],
            "tier":                    MODELS[model_id]["tier"],
            "total_runs":              len(runs),
            "successful_runs":         len(successful),
            "success_rate_pct":        round(len(successful) / len(runs) * 100, 1) if runs else 0,
            "avg_latency_ms":          safe_mean(latencies),
            "median_latency_ms":       round(statistics.median(latencies), 2) if latencies else 0,
            "p95_latency_ms":          round(sorted(latencies)[int(len(latencies) * 0.95)], 2) if len(latencies) >= 2 else 0,
            "avg_total_tokens":        safe_mean(tokens),
            "avg_completion_tokens":   safe_mean([r["completion_tokens"] for r in successful]),
            "avg_accuracy":            avg_score("accuracy"),
            "avg_helpfulness":         avg_score("helpfulness"),
            "avg_tone":                avg_score("tone"),
            "avg_conciseness":         avg_score("conciseness"),
            "avg_instruction_following": avg_score("instruction_following"),
            "avg_composite_score":     avg_score("composite"),
        }
        results["model_summary"][model_id] = summary
        print(f"  {MODELS[model_id]['label']}")
        print(f"    Success: {summary['successful_runs']}/{summary['total_runs']} | "
              f"Latency: {summary['avg_latency_ms']}ms | "
              f"Score: {summary['avg_composite_score']}/5")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✅ Results saved to: {output_path}")
    return results


# ─── Log Analysis ─────────────────────────────────────────────────────────────

def run_log_analysis(app_log: str, llm_log: str, weather_log: str,
                     output_path: str = "log_analysis.json") -> dict:
    """Parse all three log files and save analysis."""
    print("\n📊 Parsing log files...")

    # Pre-flight: show resolved paths so the user can spot wrong-directory issues
    found, missing = [], []
    for label, path in [
        ("app.jsonl",             app_log),
        ("llm_service.jsonl",     llm_log),
        ("weather_service.jsonl", weather_log),
    ]:
        abs_p = os.path.abspath(path)
        if os.path.exists(path):
            found.append(f"  ✅ {label}: {abs_p}")
        else:
            missing.append(f"  ❌ {label}: {abs_p} — NOT FOUND")

    for msg in found + missing:
        print(msg)

    if missing:
        print(f"\n⚠️  {len(missing)} log file(s) not found.")
        print("   Either copy your log files next to evaluate.py, or pass explicit paths:")
        print("   python evaluate.py --app-log /full/path/app.jsonl \\")
        print("                      --llm-log /full/path/llm_service.jsonl \\")
        print("                      --weather-log /full/path/weather_service.jsonl")
    print()

    app_stats     = parse_app_logs(app_log)
    llm_stats     = parse_llm_logs(llm_log)
    weather_stats = parse_weather_logs(weather_log)

    analysis = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "app_stats":     app_stats,
        "llm_stats":     llm_stats,
        "weather_stats": weather_stats,
        "key_findings":  generate_findings(app_stats, llm_stats, weather_stats),
    }

    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)

    print("📋 Log Analysis Summary:")
    print(f"  Total weather fetches: {app_stats.get('total_fetches', 0)}")
    print(f"  Avg fetch latency:     {app_stats.get('avg_latency_ms', 0)}ms")
    print(f"  LLM success rate:      {llm_stats.get('success_rate_pct', 0)}%")
    print(f"  Avg LLM latency:       {llm_stats.get('avg_latency_ms', 0)}ms")
    print(f"  Avg tokens/call:       {llm_stats.get('avg_tokens', 0)}")
    print(f"  Rate limit errors:     {llm_stats.get('rate_limit_errors', 0)}")
    print(f"  TPD utilization:       {llm_stats.get('tpd_utilization_pct', 0)}%")
    print(f"\n✅ Log analysis saved to: {output_path}")
    return analysis


def generate_findings(app_stats: dict, llm_stats: dict, weather_stats: dict) -> list:
    """Auto-generate key findings and recommendations from log data."""
    findings = []

    rl_errors = llm_stats.get("rate_limit_errors", 0)
    tpd_pct   = llm_stats.get("tpd_utilization_pct", 0)
    if rl_errors > 0:
        findings.append({
            "severity": "critical",
            "category": "Rate Limits",
            "finding": f"{rl_errors} rate limit errors detected. You hit Groq's 100K TPD cap ({tpd_pct}% utilization).",
            "recommendation": "Upgrade to Groq Dev Tier or implement request queuing + exponential backoff. Consider caching LLM responses for repeated cities.",
        })

    max_lat = app_stats.get("max_latency_ms", 0)
    avg_lat = app_stats.get("avg_latency_ms", 0)
    if max_lat > 30000:
        findings.append({
            "severity": "warning",
            "category": "Latency",
            "finding": f"Extreme latency spike: {max_lat:.0f}ms max vs {avg_lat:.0f}ms avg. Likely first-ever historical data fetch (5-year data download).",
            "recommendation": "Pre-warm the historical data cache on app startup, or fetch it asynchronously.",
        })

    avg_tokens = llm_stats.get("avg_tokens", 0)
    if avg_tokens > 800:
        findings.append({
            "severity": "info",
            "category": "Token Efficiency",
            "finding": f"Average {avg_tokens} tokens/call. At 100K TPD you can serve ~{int(100000 / avg_tokens)} insights/day on the free tier.",
            "recommendation": "Trim the system prompt or use a smaller model for high-volume scenarios.",
        })

    success_rate = llm_stats.get("success_rate_pct", 100)
    if success_rate < 90:
        findings.append({
            "severity": "warning",
            "category": "Reliability",
            "finding": f"LLM success rate is {success_rate}% — below the 90% threshold.",
            "recommendation": "Implement retry logic with exponential backoff and a static fallback template.",
        })

    findings.append({
        "severity": "info",
        "category": "Performance Bottleneck",
        "finding": "5-year historical data fetch is the main latency driver (early entries >20s; subsequent ~5s).",
        "recommendation": "Cache historical summaries by (lat, lon, month) in your DB. This data changes at most monthly.",
    })

    return findings


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WeatherTwin LLM Evaluation Suite")
    parser.add_argument("--groq-key",    type=str, default=os.getenv("GROQ_API_KEY",   ""),
                        help="Groq API key (or set GROQ_API_KEY env var)")
    parser.add_argument("--deepseek-key",  type=str, default=os.getenv("DEEPSEEK_API_KEY", ""),
                        help="DeepSeek API key (or set DEEPSEEK_API_KEY env var)")
    parser.add_argument("--skip-live",   action="store_true",
                        help="Only parse logs, skip live model evaluation")
    parser.add_argument("--app-log",     default="/Users/sayush/Downloads/LatestWeatherTwin/logs/app.jsonl",
                        help="Path to app.jsonl (default: ./app.jsonl)")
    parser.add_argument("--llm-log",     default="/Users/sayush/Downloads/LatestWeatherTwin/logs/llm_service.jsonl",
                        help="Path to llm_service.jsonl")
    parser.add_argument("--weather-log", default="/Users/sayush/Downloads/LatestWeatherTwin/logs/weather_service.jsonl",
                        help="Path to weather_service.jsonl")
    parser.add_argument("--output",      default="/Users/sayush/Downloads/LatestWeatherTwin/eval_results.json",
                        help="Output file for eval results")
    parser.add_argument("--delay",       type=float, default=2.0,
                        help="Seconds between Groq API calls (default: 2.0)")
    args = parser.parse_args()

    log_analysis = run_log_analysis(args.app_log, args.llm_log, args.weather_log)

    if not args.skip_live:
        missing_keys = []
        if not args.groq_key:   missing_keys.append("--groq-key   (GROQ_API_KEY)")
        if not args.deepseek_key: missing_keys.append("--deepseek-key (DEEPSEEK_API_KEY)")

        if missing_keys:
            print("\n❌ Missing required keys for live evaluation:")
            for k in missing_keys:
                print(f"   {k}")
            print("\n   Usage:  python evaluate.py --groq-key GK --deepseek-key DSK")
            print("   Logs only: python evaluate.py --skip-live")
        else:
            eval_results = run_evaluation(
                groq_key=args.groq_key,
                deepseek_key=args.deepseek_key,
                output_path=args.output,
                rate_limit_delay=args.delay,
            )
            if eval_results:
                eval_results["log_analysis"] = log_analysis
                with open(args.output, "w") as f:
                    json.dump(eval_results, f, indent=2, default=str)
                print(f"\n🎉 Done! Open the dashboard: streamlit run eval_dashboard.py")