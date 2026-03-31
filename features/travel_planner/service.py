"""
Travel Planner — core business logic.
Destination profiles, health-aware packing, mode-aware itinerary,
weather comparison, driving route, and risk assessment via LLM.
Also includes: Road Condition Predictor, Best Travel Window, Flight Delay Risk.
"""

import asyncio
import time
import requests as sync_requests
import httpx
from datetime import datetime, timedelta
from config import client, MODEL
from .models import (
    TravelReport, BlackIceRisk, FogRisk, RoadConditionHour,
    RoadConditions, TravelWindowDay, TravelWindowResult,
    FlightDelayRisk, FlightDelayResult,
)


def _run_async(coro):
    """Run an async coroutine from sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _llm_call(system_prompt: str, user_prompt: str, temperature: float = 0.6, max_tokens: int = 300, retries: int = 3) -> str:
    """Async LLM call with retry logic for connection errors."""
    for attempt in range(retries):
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))  # Back-off: 1.5s, 3s
                continue
            raise e


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
    """Generate a comprehensive travel weather report."""
    date_info = f"from {start_date} to {end_date} ({num_days} days)" if start_date else (f" in {month}" if month else "")

    profile = _get_destination_profile(destination, date_info)
    packing = _get_packing_list(destination, date_info, health_issues, travel_mode)
    itinerary = _generate_itinerary(destination, date_info, num_days, travel_mode)
    weather_diff = _compare_weather(destination, home_city, date_info) if home_city else "Set your home address in the sidebar to see weather comparison."
    risk = _assess_risk(destination, date_info, travel_mode)

    # Route for car mode
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
        profile=profile,
        packing_list=packing,
        weather_twin="",
        flight_risk=risk,
        itinerary=itinerary,
        weather_diff=weather_diff,
        route_coords=route_coords,
        home_coords=home_coords,
        dest_coords=dest_coords,
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


def _assess_risk(destination: str, date_info: str, travel_mode: str) -> str:
    if travel_mode == "Car":
        sys_p = "You are a road travel weather expert. Rate driving weather risk as Low, Moderate, or High. Mention hazards. Max 150 chars."
        usr_p = f"Driving weather risk for road trip to {destination} {date_info}?"
    else:
        sys_p = "You are an aviation weather expert. Rate flight disruption risk as Low, Moderate, or High with reason. Max 150 chars."
        usr_p = f"Flight disruption risk for travel to {destination} {date_info}?"
    try:
        return _run_async(_llm_call(sys_p, usr_p, temperature=0.3, max_tokens=80))
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


def fetch_road_weather(lat: float, lon: float) -> dict:
    """Fetch road-specific weather variables from Open-Meteo."""
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
        "daily": [
            "temperature_2m_min",
            "temperature_2m_max",
            "precipitation_sum",
            "snowfall_sum",
        ],
        "forecast_days": 7,
        "timezone": "auto",
    }
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


def compute_road_conditions(road_data: dict) -> RoadConditions:
    """Master road condition analyzer — next 24 hours."""
    if "error" in road_data:
        return RoadConditions()

    hourly = road_data.get("hourly", {})
    times = hourly.get("time", [])
    results = []

    for i in range(min(24, len(times))):
        ice = compute_black_ice_probability(hourly, i)
        fog = compute_fog_risk(hourly, i)

        # Combined danger score
        fog_score = (100 if fog.visibility_m < 200 else
                     60 if fog.visibility_m < 500 else
                     30 if fog.visibility_m < 1000 else 0)
        combined_score = max(ice.risk_score, fog_score)

        time_label = times[i][11:16] if len(times[i]) > 11 else times[i]
        results.append(RoadConditionHour(
            hour=i,
            time_label=time_label,
            ice=ice,
            fog=fog,
            combined_danger=combined_score,
            safe_to_drive=combined_score < 30,
        ))

    if not results:
        return RoadConditions()

    worst = max(results, key=lambda x: x.combined_danger)
    safe_windows = [r for r in results if r.safe_to_drive]

    return RoadConditions(
        hourly=results,
        worst_hour=worst,
        safe_hours_count=len(safe_windows),
        current=results[0],
        peak_danger_time=worst.time_label,
        peak_danger_score=worst.combined_danger,
    )


# ═══════════════════════════════════════════════════
#  NEW FEATURE 2: Best Travel Window
# ═══════════════════════════════════════════════════

def compute_travel_window(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    trip_hours: float = 4.0,
) -> TravelWindowResult:
    """
    Fetches weather at origin, destination, and midpoint.
    Scores each day 0–100 for travel safety.
    """
    mid_lat = (origin_lat + dest_lat) / 2
    mid_lon = (origin_lon + dest_lon) / 2

    # Fetch all three points
    origin_data = fetch_road_weather(origin_lat, origin_lon)
    dest_data = fetch_road_weather(dest_lat, dest_lon)
    mid_data = fetch_road_weather(mid_lat, mid_lon)

    if any("error" in d for d in [origin_data, dest_data, mid_data]):
        return TravelWindowResult(trip_hours=trip_hours)

    daily_scores = []
    origin_daily = origin_data.get("daily", {})
    dest_daily = dest_data.get("daily", {})
    num_days = min(7, len(origin_daily.get("time", [])))

    for i in range(num_days):
        day_scores = []

        for point_data, label in [
            (origin_data, "origin"),
            (mid_data, "midpoint"),
            (dest_data, "destination"),
        ]:
            d = point_data.get("daily", {})
            temp_min_list = d.get("temperature_2m_min", [])
            temp_max_list = d.get("temperature_2m_max", [])
            precip_list = d.get("precipitation_sum", [])
            snow_list = d.get("snowfall_sum", [])

            temp_min = temp_min_list[i] if i < len(temp_min_list) and temp_min_list[i] is not None else 10
            temp_max = temp_max_list[i] if i < len(temp_max_list) and temp_max_list[i] is not None else 20
            precip = precip_list[i] if i < len(precip_list) and precip_list[i] is not None else 0
            snow = snow_list[i] if i < len(snow_list) and snow_list[i] is not None else 0

            # Score this point/day
            score = 100

            # Precipitation penalty
            if precip > 20:
                score -= 40
            elif precip > 10:
                score -= 25
            elif precip > 2:
                score -= 10

            # Snow penalty (heavy)
            if snow > 10:
                score -= 50
            elif snow > 2:
                score -= 30
            elif snow > 0:
                score -= 15

            # Freezing conditions
            if temp_min <= 0 and precip > 0:
                score -= 25
            if temp_min <= -10:
                score -= 15

            day_scores.append({"point": label, "score": max(0, score)})

        # Worst point in the corridor determines the day's score
        corridor_score = min(s["score"] for s in day_scores)
        worst_point = min(day_scores, key=lambda x: x["score"])

        # Get day label
        day_label = (datetime.now() + timedelta(days=i)).strftime("%A, %b %d")
        if i == 0:
            day_label = "Today"
        if i == 1:
            day_label = "Tomorrow"

        origin_time_list = origin_daily.get("time", [])
        date_str = origin_time_list[i] if i < len(origin_time_list) else ""

        origin_precip_list = origin_daily.get("precipitation_sum", [])
        dest_precip_list = dest_daily.get("precipitation_sum", [])
        origin_snow_list = origin_daily.get("snowfall_sum", [])

        daily_scores.append(TravelWindowDay(
            day=day_label,
            date=date_str,
            corridor_score=corridor_score,
            worst_point=worst_point["point"],
            grade=("🟢 Excellent" if corridor_score >= 85 else
                   "🟡 Good" if corridor_score >= 70 else
                   "🟠 Fair" if corridor_score >= 50 else
                   "🔴 Poor — consider postponing"),
            origin_precip=origin_precip_list[i] if i < len(origin_precip_list) and origin_precip_list[i] is not None else 0,
            dest_precip=dest_precip_list[i] if i < len(dest_precip_list) and dest_precip_list[i] is not None else 0,
            origin_snow=origin_snow_list[i] if i < len(origin_snow_list) and origin_snow_list[i] is not None else 0,
        ))

    best_day = max(daily_scores, key=lambda x: x.corridor_score) if daily_scores else None

    return TravelWindowResult(
        daily_scores=daily_scores,
        best_travel_day=best_day,
        trip_hours=trip_hours,
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
