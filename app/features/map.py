"""
Interactive weather map — Folium-based map with weather markers and layers.
"""

import folium
from folium import plugins

from config import OPENWEATHER_API_KEY
from agent.tools import get_quick_weather


def create_weather_map(center_lat=39.8283, center_lon=-98.5795, zoom=4):
    """
    Create interactive weather map with real-time layers.
    Uses OpenWeatherMap tiles for live weather visualization.
    """
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # ── Extra tile layers ──
    folium.TileLayer(
        tiles="https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png",
        attr=(
            'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under '
            '<a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. '
            'Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under ODbL.'
        ),
        name="Terrain",
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="CartoDB positron",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="Light Mode",
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="CartoDB dark_matter",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="Dark Mode",
        overlay=False,
        control=True,
    ).add_to(m)

    # ── OpenWeatherMap overlay layers ──
    if OPENWEATHER_API_KEY:
        owm_layers = [
            ("temp_new", "🌡️ Temperature"),
            ("precipitation_new", "🌧️ Precipitation"),
            ("clouds_new", "☁️ Clouds"),
            ("wind_new", "💨 Wind Speed"),
            ("pressure_new", "🌡️ Pressure"),
        ]
        for layer_id, label in owm_layers:
            folium.TileLayer(
                tiles=f"https://tile.openweathermap.org/map/{layer_id}/{{z}}/{{x}}/{{y}}.png?appid={OPENWEATHER_API_KEY}",
                attr='&copy; <a href="https://openweathermap.org/">OpenWeatherMap</a>',
                name=label,
                overlay=True,
                control=True,
                opacity=0.6,
            ).add_to(m)

    # ── City markers ──
    major_cities = [
        {"name": "New York", "lat": 40.7128, "lon": -74.0060},
        {"name": "Los Angeles", "lat": 34.0522, "lon": -118.2437},
        {"name": "Chicago", "lat": 41.8781, "lon": -87.6298},
        {"name": "Miami", "lat": 25.7617, "lon": -80.1918},
        {"name": "Seattle", "lat": 47.6062, "lon": -122.3321},
        {"name": "London", "lat": 51.5074, "lon": -0.1278},
        {"name": "Paris", "lat": 48.8566, "lon": 2.3522},
        {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
        {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
        {"name": "Dubai", "lat": 25.2048, "lon": 55.2708},
    ]

    for city in major_cities:
        weather_info = get_quick_weather(city["name"])

        temp = weather_info.get("temp", 20)
        if isinstance(temp, str):
            temp = 20

        if temp < 0:
            color = "blue"
        elif temp < 10:
            color = "lightblue"
        elif temp < 20:
            color = "green"
        elif temp < 30:
            color = "orange"
        else:
            color = "red"

        popup_html = f"""
        <div style="font-family: Arial; width: 200px;">
            <h4 style="margin: 0;">{city['name']}</h4>
            <hr style="margin: 5px 0;">
            <p style="margin: 5px 0;"><b>🌡️ Temp:</b> {weather_info.get('temp', 'N/A')}°C</p>
            <p style="margin: 5px 0;"><b>☁️ Condition:</b> {weather_info.get('condition', 'N/A')}</p>
            <p style="margin: 5px 0;"><b>💧 Humidity:</b> {weather_info.get('humidity', 'N/A')}%</p>
            <p style="margin: 5px 0;"><b>💨 Wind:</b> {weather_info.get('wind', 'N/A')} km/h</p>
            <small>Click anywhere to view full details</small>
        </div>
        """

        folium.Marker(
            location=[city["lat"], city["lon"]],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{city['name']}: {weather_info.get('temp', 'N/A')}°C",
            icon=folium.Icon(color=color, icon="info-sign"),
        ).add_to(m)

    # ── Map controls ──
    minimap = plugins.MiniMap(toggle_display=True)
    m.add_child(minimap)
    plugins.MeasureControl(position="topleft", primary_length_unit="kilometers").add_to(m)
    plugins.Fullscreen(position="topleft").add_to(m)
    plugins.MousePosition().add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)

    return m
