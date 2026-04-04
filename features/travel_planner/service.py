"""
Travel Planner — core business logic.
Destination profiles, health-aware packing, mode-aware itinerary,
weather comparison, driving route, and risk assessment via LLM.
Also includes: Road Condition Predictor and Flight Delay Risk.
"""

import asyncio
import json
import time
import os
import requests as sync_requests
import httpx
from datetime import datetime, timedelta
from config import client, MODEL, MODEL_SMALL
from .models import (
    TravelReport, BlackIceRisk, FogRisk, WindRisk, RainRisk,
    RoadConditionHour, RoadConditions,
    FlightDelayRisk, FlightDelayResult,
)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "travel_cache.json")

def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def _save_cache(cache_data):
    try:
        # Keep only last 100 entries to prevent file bloat
        if len(cache_data) > 100:
            keys = list(cache_data.keys())
            for k in keys[:20]:
                del cache_data[k]
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except:
        pass


def _run_async(coro):
    """Run an async coroutine from sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _llm_call(system_prompt: str, user_prompt: str, temperature: float = 0.6, max_tokens: int = 300, retries: int = 3, force_model: str = None) -> str:
    """Async LLM call with retry logic and model fallback (429 handling)."""
    current_model = force_model or MODEL
    
    for attempt in range(retries):
        try:
            response = await client.chat.completions.create(
                model=current_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_msg = str(e).lower()
            # If 429 (rate limit) or 503/504 (overloaded), try fallback to 8B model
            if "429" in err_msg or "rate limit" in err_msg:
                if current_model == MODEL:
                    current_model = MODEL_SMALL
                    # Wait briefly before switching
                    await asyncio.sleep(1)
                    continue
            
            if attempt < retries - 1:
                # Use non-blocking sleep in async context
                await asyncio.sleep(2 * (attempt + 1))
                continue
            raise e


async def _get_consolidated_travel_data(destination: str, date_info: str, num_days: int, travel_mode: str, home_city: str, health_issues: str) -> dict:
    """Fetch all AI components in a single consolidated JSON request to save tokens and avoid rate limits."""
    health_ctx = f"Traveler health conditions: {health_issues}." if health_issues else ""
    mode_ctx = "Traveling by car (road trip)." if travel_mode == "Car" else "Traveling by flight."
    comparison_ctx = f"Compare with home city: {home_city}." if home_city else ""
    
    prompt = (
        f"Generate a comprehensive travel weather report for **{destination}** during the period: **{date_info}**. "
        f"{mode_ctx} {health_ctx} {comparison_ctx}\n\n"
        "Return the response in EXACT JSON format with these keys. IMPORTANT: All values MUST be plain strings (use markdown for formatting), NOT nested objects or lists:\n"
        "- 'profile': Brief weather profile (highs/lows, rain days, humidity, tip). Use bullet points. Value must be a string.\n"
        "- 'packing': Category-based list with emojis. Include health/mode needs. Bullet points. Value must be a string.\n"
        "- 'itinerary': Day-by-day plan for {num_days} days. Use 'Day X' format with emojis. Concise. Value must be a string.\n"
        "- 'weather_diff': Comparison summary between home and destination. Value must be a string.\n"
        "- 'risk': Risk assessment (Low/Moderate/High) with a brief reason. Value must be a string.\n\n"
        "Double check that every value in the JSON is a string."
    )
    
    try:
        raw_json = await _llm_call(
            "You are a helpful travel weather AI. You response ONLY in structured JSON.",
            prompt,
            temperature=0.6,
            max_tokens=2000 # Increased to handle full report
        )
        # Clean up in case there's markdown around it
        clean_json = raw_json.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        
        result = json.loads(clean_json.strip())
        # Safety: Flatten any nested structures into strings to prevent Pydantic validation errors
        return {k: _flatten_to_string(v) for k, v in result.items()}
    except Exception as e:
        print(f"Consolidated AI call failed: {e}")
        return {}

def _flatten_to_string(val) -> str:
    """Helper to convert nested dicts/lists from AI into a flat readable string."""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return "\n".join([f"- **{k.title()}**: {v}" if not isinstance(v, (dict, list)) else f"- **{k.title()}**:\n{_flatten_to_string(v)}" for k, v in val.items()])
    if isinstance(val, list):
        return "\n".join([f"- {v}" if not isinstance(v, (dict, list)) else _flatten_to_string(v) for v in val])
    return str(val)


def get_travel_report(
    destination: str,
    month: str = "",
    start_date: str = "",
    end_date: str = "",
    num_days: int = 1,
    home_city: str = "",
    health_issues: str = "",
    travel_mode: str = "Flight",
) -> TravelReport:
    """Generate a comprehensive travel weather report with caching and fallback."""
    date_info = f"from {start_date} to {end_date} ({num_days} days)" if start_date else (f" in {month}" if month else "")
    
    # ── Caching Logic ──
    cache = _load_cache()
    cache_key = f"{destination}_{month}_{start_date}_{end_date}_{travel_mode}_{home_city}_{health_issues}".lower().replace(" ", "_")
    
    if cache_key in cache:
        cached_data = cache[cache_key]
        # Check if cache is reasonably fresh (e.g., within 24 hours) - simplified for now
        return TravelReport(
            destination=destination,
            month=month,
            start_date=start_date,
            end_date=end_date,
            num_days=num_days,
            home_city=home_city,
            health_issues=health_issues,
            travel_mode=travel_mode,
            profile=cached_data.get("profile", "Profile unavailable"),
            packing_list=cached_data.get("packing", "Packing list unavailable"),
            weather_twin="",
            flight_risk=cached_data.get("risk", "Risk assessment unavailable"),
            itinerary=cached_data.get("itinerary", "Itinerary unavailable"),
            weather_diff=cached_data.get("weather_diff", "Comparison unavailable"),
            route_coords=[], # Real-time route is calculated below
            home_coords=None,
            dest_coords=None,
            is_cached=True # Meta field for UI
        )

    # ── Fetch Consolidated Data ──
    try:
        ai_data = _run_async(_get_consolidated_travel_data(destination, date_info, num_days, travel_mode, home_city, health_issues))
    except:
        ai_data = {}

    # ── Fallback to individual calls if consolidated failed or returned empty ──
    if not ai_data:
        profile = _get_destination_profile(destination, date_info)
        packing = _get_packing_list(destination, date_info, health_issues, travel_mode)
        itinerary = _generate_itinerary(destination, date_info, num_days, travel_mode)
        weather_diff = _compare_weather(destination, home_city, date_info) if home_city else "Set your home address in the sidebar to see weather comparison."
        risk = _assess_risk(home_city, destination, date_info, travel_mode)
        
        ai_data = {
            "profile": profile,
            "packing": packing,
            "itinerary": itinerary,
            "weather_diff": weather_diff,
            "risk": risk
        }

    # Save to Cache
    cache[cache_key] = ai_data
    _save_cache(cache)

    # ── Real-time routing (non-AI) ──
    route_coords = []
    home_coords = None
    dest_coords = None
    if travel_mode == "Car" and home_city:
        home_coords, dest_coords, route_coords = _get_driving_route(home_city, destination)

    return TravelReport(
        destination=destination,
        month=month,
        start_date=start_date,
        end_date=end_date,
        num_days=num_days,
        home_city=home_city,
        health_issues=health_issues,
        travel_mode=travel_mode,
        profile=ai_data.get("profile", ""),
        packing_list=ai_data.get("packing", ""),
        weather_twin="",
        flight_risk=ai_data.get("risk", ""),
        itinerary=ai_data.get("itinerary", ""),
        weather_diff=ai_data.get("weather_diff", ""),
        route_coords=route_coords,
        home_coords=home_coords,
        dest_coords=dest_coords,
        is_cached=False
    )


def _get_destination_profile(destination: str, date_info: str) -> str:
    try:
        return _run_async(_llm_call(
            "You are a travel weather expert. Give a brief destination weather profile with average highs/lows, rain days, humidity, and one key tip. Use bullet points. Max 400 chars.",
            f"Weather profile for {destination} {date_info}?",
            temperature=0.6, max_tokens=200,
        ))
    except Exception as e:
        return f"Profile unavailable: {e}"


def _get_packing_list(destination: str, date_info: str, health_issues: str, travel_mode: str) -> str:
    health_ctx = f"\n\nIMPORTANT: The traveler has these health conditions: {health_issues}. Include relevant medications, protective gear, and health precautions in the packing list." if health_issues else ""
    mode_ctx = "traveling by car (road trip)" if travel_mode == "Car" else "traveling by flight"
    try:
        return _run_async(_llm_call(
            f"You are a travel packing advisor. The traveler is {mode_ctx}. Give a well-organized packing list based on weather, using categories with emojis (👕 Clothing, 💊 Health, 🧴 Essentials). Bullet points. Max 600 chars.{health_ctx}",
            f"What should I pack for {destination} {date_info}?",
            temperature=0.6, max_tokens=350,
        ))
    except Exception as e:
        return f"Packing list unavailable: {e}"


def _generate_itinerary(destination: str, date_info: str, num_days: int, travel_mode: str) -> str:
    mode_ctx = ""
    if travel_mode == "Car":
        mode_ctx = " The traveler is driving. Include driving tips, scenic routes, and rest stops."
    else:
        mode_ctx = " The traveler is flying. Include airport transfer tips for arrival day."
    try:
        return _run_async(_llm_call(
            f"You are a travel itinerary expert. Create a day-by-day plan for {num_days} days with must-visit spots, local food, and weather-appropriate activities. Use Day 1, Day 2 format with emojis. Be concise.{mode_ctx}",
            f"Create a {num_days}-day itinerary for {destination} {date_info}.",
            temperature=0.7, max_tokens=500,
        ))
    except Exception as e:
        return f"Itinerary unavailable: {e}"


def _compare_weather(destination: str, home_city: str, date_info: str) -> str:
    try:
        return _run_async(_llm_call(
            "You are a weather comparison expert. Compare weather of two cities. Highlight key differences in temperature, humidity, precipitation. Use emojis. Max 400 chars.",
            f"Compare weather: {home_city} vs {destination} {date_info}. Key differences?",
            temperature=0.6, max_tokens=250,
        ))
    except Exception as e:
        return f"Comparison unavailable: {e}"


def _assess_risk(home_city: str, destination: str, date_info: str, travel_mode: str) -> str:
    dep = home_city or "Departure"
    if travel_mode == "Car":
        sys_p = "You are a road travel weather expert. Rate driving weather risk as Low, Moderate, or High. Mention hazards. Max 150 chars."
        usr_p = f"Driving weather risk for road trip from {dep} to {destination} {date_info}?"
    else:
        sys_p = "You are an aviation weather expert. Rate flight disruption risk as Low, Moderate, or High with reason. Max 200 chars. Mention both locations."
        usr_p = f"Flight disruption risk for flights between {dep} and {destination} {date_info}?"
    try:
        return _run_async(_llm_call(sys_p, usr_p, temperature=0.3, max_tokens=100))
    except Exception:
        return "Low"




async def _geocode_city(name: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.get(url, params={"name": name.replace(",", " ").strip(), "count": 1, "language": "en"})
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results")
    if results:
        return (results[0]["latitude"], results[0]["longitude"])
    return None


def _get_driving_route(home_city: str, destination: str):
    try:
        home_ll = _run_async(_geocode_city(home_city))
        dest_ll = _run_async(_geocode_city(destination))
        if not home_ll or not dest_ll:
            return None, None, []
        url = f"https://router.project-osrm.org/route/v1/driving/{home_ll[1]},{home_ll[0]};{dest_ll[1]},{dest_ll[0]}?overview=full&geometries=geojson"
        with httpx.Client(timeout=15) as c:
            resp = c.get(url)
            resp.raise_for_status()
            data = resp.json()
        if data.get("routes"):
            geojson_coords = data["routes"][0]["geometry"]["coordinates"]
            route = [(coord[1], coord[0]) for coord in geojson_coords]
            return home_ll, dest_ll, route
        return home_ll, dest_ll, []
    except Exception:
        return None, None, []


# ═══════════════════════════════════════════════════
#  NEW FEATURE 1: Road Condition Predictor
# ═══════════════════════════════════════════════════

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_road_weather(lat: float, lon: float, start_date: str = None, end_date: str = None) -> dict:
    """Fetch road-specific weather variables from Open-Meteo for the trip duration."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m",
            "dewpoint_2m",
            "precipitation",
            "rain",
            "snowfall",
            "snow_depth",
            "visibility",
            "wind_speed_10m",
        ],
        "timezone": "auto",
    }
    
    if start_date and end_date:
        # Open-Meteo supports up to 16 days in the future.
        # Ensure we don't request dates beyond that limit.
        today = datetime.now().date()
        max_date = today + timedelta(days=15)
        
        try:
            s_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            e_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            if s_date_obj > max_date:
                s_date_obj = max_date
            if e_date_obj > max_date:
                e_date_obj = max_date
            
            if s_date_obj <= e_date_obj:
                params["start_date"] = s_date_obj.strftime("%Y-%m-%d")
                params["end_date"] = e_date_obj.strftime("%Y-%m-%d")
            else:
                params["forecast_days"] = 7
        except:
            params["forecast_days"] = 7
    else:
        params["forecast_days"] = 7
        
    try:
        resp = sync_requests.get(OPENMETEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def compute_black_ice_probability(hourly: dict, hour_index: int) -> BlackIceRisk:
    """
    Black ice forms when:
    1. Surface temp at or below 0°C
    2. Moisture present (recent rain, dew, or snow melt)
    3. Often AFTER a freeze-thaw cycle
    Most dangerous: 11pm–7am when roads aren't treated
    """
    temps = hourly.get("temperature_2m", [])
    if hour_index >= len(temps) or temps[hour_index] is None:
        return BlackIceRisk(risk_score=0, condition="NO DATA", icon="❓",
                           risk_factors=["Insufficient data"])

    temp = temps[hour_index]
    dewpoints = hourly.get("dewpoint_2m", [])
    dewpoint = dewpoints[hour_index] if hour_index < len(dewpoints) and dewpoints[hour_index] is not None else temp - 5
    precip_list = hourly.get("precipitation", [])
    precip = precip_list[hour_index] if hour_index < len(precip_list) and precip_list[hour_index] is not None else 0
    rain_list = hourly.get("rain", [])
    rain_prev3 = sum(
        (rain_list[j] or 0) for j in range(max(0, hour_index - 3), hour_index)
        if j < len(rain_list)
    )
    snowfall_list = hourly.get("snowfall", [])
    snowfall = snowfall_list[hour_index] if hour_index < len(snowfall_list) and snowfall_list[hour_index] is not None else 0
    snow_depth_list = hourly.get("snow_depth", [])
    snow_depth = snow_depth_list[hour_index] if hour_index < len(snow_depth_list) and snow_depth_list[hour_index] is not None else 0

    # Use air temp as surface temp proxy (Open-Meteo surface_temperature
    # may not always be available)
    surface_temp = temp

    risk_score = 0
    factors = []

    # Factor 1: Surface temperature at or near freezing
    if surface_temp <= 0:
        risk_score += 40
        factors.append(f"Road surface at {surface_temp:.1f}°C (at/below freezing)")
    elif surface_temp <= 2:
        risk_score += 20
        factors.append(f"Road surface near freezing ({surface_temp:.1f}°C)")

    # Factor 2: Recent rain on cold surface = instant black ice
    if rain_prev3 > 0.5 and surface_temp <= 2:
        risk_score += 30
        factors.append(f"Recent rain ({rain_prev3:.1f}mm) on near-freezing surface")

    # Factor 3: Freeze-thaw cycle (air temp crossing 0 recently)
    temps_past6 = [temps[j] for j in range(max(0, hour_index - 6), hour_index)
                   if j < len(temps) and temps[j] is not None]
    if temps_past6:
        had_thaw = any(t > 2 for t in temps_past6)
        now_freezing = temp <= 0
        if had_thaw and now_freezing:
            risk_score += 20
            factors.append("Freeze-thaw cycle detected — melted moisture refreezing")

    # Factor 4: Dewpoint spread (condensation → frost)
    dew_spread = temp - dewpoint
    if dew_spread <= 1 and temp <= 3:
        risk_score += 15
        factors.append(f"Dewpoint near air temp ({dew_spread:.1f}°C spread) — frost forming")

    # Factor 5: Snow depth (packed snow → ice)
    if snow_depth > 0 and surface_temp <= 0:
        risk_score += 10
        factors.append(f"Snow pack present ({snow_depth}cm) — compaction ice risk")

    # Factor 6: Active snowfall
    if snowfall > 0:
        risk_score += 15
        factors.append(f"Active snowfall ({snowfall}cm/hr)")

    risk_score = min(risk_score, 100)

    # Stopping distance multipliers (from UK Highway Code research)
    if risk_score >= 70:
        stopping_multiplier = 10
        condition = "BLACK ICE LIKELY"
        icon = "🔴"
    elif risk_score >= 40:
        stopping_multiplier = 3
        condition = "ICY PATCHES POSSIBLE"
        icon = "🟠"
    elif risk_score >= 20:
        stopping_multiplier = 2
        condition = "SLIPPERY CONDITIONS"
        icon = "🟡"
    else:
        stopping_multiplier = 1
        condition = "NORMAL CONDITIONS"
        icon = "🟢"

    return BlackIceRisk(
        risk_score=risk_score,
        condition=condition,
        icon=icon,
        stopping_distance_multiplier=stopping_multiplier,
        risk_factors=factors,
        surface_temp_c=round(surface_temp, 1),
        air_temp_c=round(temp, 1),
    )


def compute_fog_risk(hourly: dict, hour_index: int) -> FogRisk:
    """
    Radiation fog forms on clear nights when humidity is high.
    Advection fog forms when warm moist air moves over cold surface.
    """
    vis_list = hourly.get("visibility", [])
    visibility = vis_list[hour_index] if hour_index < len(vis_list) and vis_list[hour_index] is not None else 10000
    temps = hourly.get("temperature_2m", [])
    temp = temps[hour_index] if hour_index < len(temps) and temps[hour_index] is not None else 15
    dew_list = hourly.get("dewpoint_2m", [])
    dewpoint = dew_list[hour_index] if hour_index < len(dew_list) and dew_list[hour_index] is not None else temp - 5
    dew_spread = temp - dewpoint

    # Fog = visibility < 1000m (legal definition in most countries)
    if visibility < 200:
        density, icon = "DENSE FOG", "🔴"
        speed_advice = "Do not drive — or max 20 km/h with hazard lights"
    elif visibility < 500:
        density, icon = "THICK FOG", "🟠"
        speed_advice = "Reduce speed to 40 km/h, use low beam headlights"
    elif visibility < 1000:
        density, icon = "MODERATE FOG", "🟡"
        speed_advice = "Reduce speed, increase following distance to 4 seconds"
    elif dew_spread <= 2 and temp <= 10:
        density, icon = "FOG POSSIBLE", "🟡"
        speed_advice = "Be alert — fog may form, especially in valleys and low areas"
    else:
        density, icon = "CLEAR", "🟢"
        speed_advice = "Normal driving conditions"

    return FogRisk(
        visibility_m=visibility,
        density=density,
        icon=icon,
        speed_advice=speed_advice,
        dew_spread=round(dew_spread, 1),
    )

def compute_wind_risk(hourly: dict, hour_index: int) -> WindRisk:
    """Assess wind hazard for driving — crosswinds, gusts, vehicle stability."""
    wind_list = hourly.get("wind_speed_10m", [])
    speed = wind_list[hour_index] if hour_index < len(wind_list) and wind_list[hour_index] is not None else 0

    # Open-Meteo wind_speed_10m is in km/h
    risk_score = 0
    if speed >= 90:
        level, icon = "EXTREME", "🔴"
        risk_score = 90
    elif speed >= 60:
        level, icon = "DANGEROUS", "🔴"
        risk_score = 70
    elif speed >= 40:
        level, icon = "STRONG", "🟠"
        risk_score = 40
    elif speed >= 25:
        level, icon = "MODERATE", "🟡"
        risk_score = 20
    else:
        level, icon = "CALM", "🟢"
        risk_score = 0

    return WindRisk(speed_kmh=round(speed, 1), gust_kmh=0, level=level, icon=icon, risk_score=risk_score)


def compute_rain_risk(hourly: dict, hour_index: int) -> RainRisk:
    """Assess precipitation hazard — hydroplaning, snow accumulation."""
    precip_list = hourly.get("precipitation", [])
    rain_list = hourly.get("rain", [])
    snow_list = hourly.get("snowfall", [])
    depth_list = hourly.get("snow_depth", [])

    precip = precip_list[hour_index] if hour_index < len(precip_list) and precip_list[hour_index] is not None else 0
    rain = rain_list[hour_index] if hour_index < len(rain_list) and rain_list[hour_index] is not None else 0
    snow = snow_list[hour_index] if hour_index < len(snow_list) and snow_list[hour_index] is not None else 0
    depth = depth_list[hour_index] if hour_index < len(depth_list) and depth_list[hour_index] is not None else 0

    risk_score = 0
    if rain >= 10:
        level, icon = "HEAVY RAIN", "🔴"
        risk_score = 70
    elif rain >= 4:
        level, icon = "MODERATE RAIN", "🟠"
        risk_score = 40
    elif rain >= 1:
        level, icon = "LIGHT RAIN", "🟡"
        risk_score = 20
    elif snow >= 2:
        level, icon = "HEAVY SNOW", "🔴"
        risk_score = 80
    elif snow >= 0.5:
        level, icon = "MODERATE SNOW", "🟠"
        risk_score = 50
    elif snow > 0:
        level, icon = "LIGHT SNOW", "🟡"
        risk_score = 25
    elif precip > 0:
        level, icon = "DRIZZLE", "🟡"
        risk_score = 10
    else:
        level, icon = "DRY", "🟢"
        risk_score = 0

    return RainRisk(
        precip_mm=round(precip, 1), rain_mm=round(rain, 1),
        snowfall_cm=round(snow, 1), snow_depth_cm=round(depth, 1),
        level=level, icon=icon, risk_score=risk_score,
    )


def compute_road_conditions(road_data: dict) -> RoadConditions:
    """Master road condition analyzer — next 24 hours."""
    if "error" in road_data:
        return RoadConditions()

    hourly = road_data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    results = []

    for i in range(len(times)):
        ice = compute_black_ice_probability(hourly, i)
        fog = compute_fog_risk(hourly, i)
        wind = compute_wind_risk(hourly, i)
        rain = compute_rain_risk(hourly, i)
        temp = temps[i] if i < len(temps) and temps[i] is not None else 15.0

        # Combined danger score from all factors
        fog_score = (100 if fog.visibility_m < 200 else
                     60 if fog.visibility_m < 500 else
                     30 if fog.visibility_m < 1000 else 0)
        combined_score = max(ice.risk_score, fog_score, wind.risk_score, rain.risk_score)

        # Overall label
        if combined_score >= 70:
            overall_label, overall_icon = "DANGEROUS", "🔴"
        elif combined_score >= 40:
            overall_label, overall_icon = "CAUTION", "🟠"
        elif combined_score >= 20:
            overall_label, overall_icon = "FAIR", "🟡"
        else:
            overall_label, overall_icon = "GOOD", "🟢"

        if len(times[i]) > 11:
            date_part = times[i][5:10].replace("-", "/") # 04/03
            time_part = times[i][11:16]
            time_label = f"{date_part} {time_part}"
        else:
            time_label = times[i]

        results.append(RoadConditionHour(
            hour=i,
            time_label=time_label,
            ice=ice,
            fog=fog,
            wind=wind,
            rain=rain,
            temp_c=round(temp, 1),
            combined_danger=combined_score,
            safe_to_drive=combined_score < 30,
            overall_label=overall_label,
            overall_icon=overall_icon,
        ))

    if not results:
        return RoadConditions()

    worst = max(results, key=lambda x: x.combined_danger)
    safe_windows = [r for r in results if r.safe_to_drive]

    # Build advisory
    advisories = []
    if any(r.ice.risk_score >= 40 for r in results):
        advisories.append("🧊 Black ice risk detected in the next 24h")
    if any(r.fog.visibility_m < 1000 for r in results):
        advisories.append("🌫️ Fog expected — reduced visibility periods")
    if any(r.wind.risk_score >= 40 for r in results):
        advisories.append("💨 Strong winds — caution for high-profile vehicles")
    if any(r.rain.risk_score >= 40 for r in results):
        advisories.append("🌧️ Heavy precipitation — hydroplaning risk")
    advisory = " · ".join(advisories) if advisories else "✅ No significant road hazards in the next 24h"

    return RoadConditions(
        hourly=results,
        worst_hour=worst,
        safe_hours_count=len(safe_windows),
        current=results[0],
        peak_danger_time=worst.time_label,
        peak_danger_score=worst.combined_danger,
        overall_advisory=advisory,
    )




# ═══════════════════════════════════════════════════
#  NEW FEATURE 3: Flight Delay Risk
# ═══════════════════════════════════════════════════

AVIATION_BASE = "https://aviationweather.gov/api/data"


def fetch_airport_weather(icao_code: str) -> dict:
    """
    Fetch METAR (current conditions) from AviationWeather.gov.
    ICAO examples: KORD (Chicago O'Hare), KJFK (JFK), KLAX (LAX)
    """
    try:
        metar_resp = sync_requests.get(
            f"{AVIATION_BASE}/metar",
            params={"ids": icao_code, "format": "json"},
            timeout=10,
        )
        metar = metar_resp.json() if metar_resp.status_code == 200 else []
    except Exception:
        metar = []

    try:
        taf_resp = sync_requests.get(
            f"{AVIATION_BASE}/taf",
            params={"ids": icao_code, "format": "json"},
            timeout=10,
        )
        taf = taf_resp.json() if taf_resp.status_code == 200 else []
    except Exception:
        taf = []

    return {"metar": metar, "taf": taf, "icao": icao_code}


def parse_delay_risk(airport_data: dict) -> FlightDelayRisk:
    """
    Delay causes by probability:
    1. Thunderstorms (most common, unpredictable)
    2. Low visibility / fog (Ground Stop triggers)
    3. Wind shear / crosswinds (runway capacity drops)
    4. Heavy snow/ice (de-icing queues, ramp closures)
    5. Low ceilings (IFR conditions slow arrival rates)
    """
    metar = airport_data.get("metar", [])
    icao = airport_data.get("icao", "????")

    if not metar:
        return FlightDelayRisk(
            icao=icao, delay_risk_score=0, risk_level="❓ No Data",
            delay_reasons=["Airport weather data unavailable"],
            conditions_summary="No METAR available",
        )

    m = metar[0] if isinstance(metar, list) else metar

    # Extract key METAR fields
    visibility_sm = m.get("visib", 10)
    wind_speed_kt = m.get("wspd", 0)
    wind_gust_kt = m.get("wgst", 0)
    sky_conditions = m.get("clouds", [])
    wx_string = m.get("wxString", "") or ""
    temp_c = m.get("temp", 10)

    delay_score = 0
    delay_reasons = []

    # Thunderstorm — biggest delay cause
    if "TS" in wx_string:
        delay_score += 50
        delay_reasons.append("⛈️ Active thunderstorms — ground stops likely")

    # Visibility / fog
    if isinstance(visibility_sm, (int, float)):
        if visibility_sm < 0.25:
            delay_score += 45
            delay_reasons.append(f"🌫️ Near-zero visibility ({visibility_sm}sm) — Ground Stop possible")
        elif visibility_sm < 1:
            delay_score += 30
            delay_reasons.append(f"🌫️ Low visibility ({visibility_sm}sm) — IFR conditions")
        elif visibility_sm < 3:
            delay_score += 15
            delay_reasons.append(f"🌫️ Reduced visibility ({visibility_sm}sm) — reduced arrival rate")

    # Ceiling height
    for sky in sky_conditions:
        coverage = sky.get("cover", "") or ""
        height_ft = sky.get("base", 9999) or 9999
        if coverage in ["BKN", "OVC"]:
            if height_ft < 500:
                delay_score += 35
                delay_reasons.append(f"☁️ Very low ceiling ({height_ft}ft) — ILS approaches only")
            elif height_ft < 1000:
                delay_score += 20
                delay_reasons.append(f"☁️ Low ceiling ({height_ft}ft) — reduced capacity")
            break

    # Wind / crosswind
    effective_wind = max(wind_speed_kt or 0, (wind_gust_kt or 0) * 0.8)
    if effective_wind > 35:
        delay_score += 30
        delay_reasons.append(f"💨 Strong winds ({effective_wind:.0f}kt) — crosswind limits possible")
    elif effective_wind > 25:
        delay_score += 15
        delay_reasons.append(f"💨 Gusty winds ({effective_wind:.0f}kt) — reduced runway throughput")

    # Snow / ice
    if "SN" in wx_string or "FZRA" in wx_string:
        delay_score += 35
        delay_reasons.append("❄️ Snow/freezing rain — de-icing queues, ramp slowdowns")
    elif "RA" in wx_string and (temp_c or 10) <= 2:
        delay_score += 20
        delay_reasons.append("🌧️ Rain near freezing — icing risk on aircraft surfaces")

    delay_score = min(delay_score, 100)

    return FlightDelayRisk(
        icao=icao,
        delay_risk_score=delay_score,
        risk_level=("🔴 High" if delay_score >= 60 else
                    "🟠 Moderate" if delay_score >= 30 else
                    "🟢 Low"),
        delay_reasons=delay_reasons,
        visibility_sm=visibility_sm if isinstance(visibility_sm, (int, float)) else None,
        wind_kt=wind_speed_kt,
        conditions_summary=wx_string or "No significant weather",
        raw_temp_c=temp_c,
    )


def compute_flight_delay(origin_icao: str, dest_icao: str) -> FlightDelayResult:
    """Compute flight delay risk for origin + destination airports."""
    origin_wx = fetch_airport_weather(origin_icao.upper())
    dest_wx = fetch_airport_weather(dest_icao.upper())

    origin_risk = parse_delay_risk(origin_wx)
    dest_risk = parse_delay_risk(dest_wx)

    return FlightDelayResult(
        origin=origin_risk,
        destination=dest_risk,
        overall_risk=max(origin_risk.delay_risk_score, dest_risk.delay_risk_score),
    )
