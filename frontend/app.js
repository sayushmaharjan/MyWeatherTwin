/**
 * WeatherTwin — Frontend Application
 * Handles search, weather display, charts, map, chat, and comparison.
 */

// ─── State ──────────────────────────────────────
const state = {
  currentCity: null,
  weatherData: null,
  chatHistory: [],
  chatOpen: false,
  mode: 'dashboard', // 'dashboard' | 'compare'
  map: null,
  mapMarker: null,
  tempChart: null,
  histChart: null,
};

const API = ''; // Same origin

// ─── Weather Emoji Map ──────────────────────────
const WEATHER_EMOJI = {
  'sunny': '☀️', 'partly-cloudy': '⛅', 'cloudy': '☁️',
  'fog': '🌫️', 'drizzle': '🌦️', 'rain': '🌧️',
  'snow': '❄️', 'storm': '⛈️',
};

// ─── DOM References ─────────────────────────────
const $ = id => document.getElementById(id);

const els = {
  searchInput: $('searchInput'),
  searchBtn: $('searchBtn'),
  locationBtn: $('locationBtn'),
  loading: $('loading'),
  errorToast: $('errorToast'),
  welcomeState: $('welcomeState'),
  dashboard: $('dashboard'),
  insightBanner: $('insightBanner'),
  insightText: $('insightText'),
  currentTemp: $('currentTemp'),
  currentFeels: $('currentFeels'),
  currentIcon: $('currentIcon'),
  currentCondition: $('currentCondition'),
  currentLocation: $('currentLocation'),
  currentDetails: $('currentDetails'),
  severityBadge: $('severityBadge'),
  anomalyFill: $('anomalyFill'),
  anomalyMarker: $('anomalyMarker'),
  anomalyDesc: $('anomalyDesc'),
  anomalyLow: $('anomalyLow'),
  anomalyHigh: $('anomalyHigh'),
  trendBadge: $('trendBadge'),
  historicalStats: $('historicalStats'),
  hourlyScroll: $('hourlyScroll'),
  forecastScroll: $('forecastScroll'),
  mapContainer: $('mapContainer'),
  chatToggle: $('chatToggle'),
  chatPanel: $('chatPanel'),
  chatClose: $('chatClose'),
  chatMessages: $('chatMessages'),
  chatInput: $('chatInput'),
  chatSend: $('chatSend'),
  chatTyping: $('chatTyping'),
  modeDashboard: $('modeDashboard'),
  modeCompare: $('modeCompare'),
  compareSection: $('compareSection'),
  compareCity1: $('compareCity1'),
  compareCity2: $('compareCity2'),
  compareBtn: $('compareBtn'),
  compareGrid: $('compareGrid'),
};

// ─── Helpers ────────────────────────────────────
function showError(msg) {
  els.errorToast.textContent = msg;
  els.errorToast.classList.add('visible');
  setTimeout(() => els.errorToast.classList.remove('visible'), 4000);
}

function showLoading(show) {
  els.loading.classList.toggle('visible', show);
}

function formatTemp(val) {
  if (val == null) return '--';
  return `${Math.round(val)}°`;
}

function getEmoji(icon, isDay = true) {
  if (icon === 'sunny' && !isDay) return '🌙';
  return WEATHER_EMOJI[icon] || '☁️';
}

function dayName(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return 'Today';
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  if (d.toDateString() === tomorrow.toDateString()) return 'Tmrw';
  return d.toLocaleDateString('en-US', { weekday: 'short' });
}

// ─── Search ─────────────────────────────────────
async function searchCity(cityName) {
  if (!cityName.trim()) return;

  showLoading(true);
  els.searchBtn.disabled = true;

  try {
    const resp = await fetch(`${API}/api/weather/full?city=${encodeURIComponent(cityName)}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `City not found`);
    }

    const data = await resp.json();
    state.weatherData = data;
    state.currentCity = data.city.name;

    renderDashboard(data);
    saveRecentSearch(cityName);

    els.welcomeState.style.display = 'none';
    els.dashboard.classList.add('visible');
    els.searchInput.value = data.city.name;

  } catch (err) {
    showError(err.message || 'Failed to fetch weather data');
  } finally {
    showLoading(false);
    els.searchBtn.disabled = false;
  }
}

// ─── Search by Coordinates (map click / geolocation) ────
async function searchByCoords(lat, lon, opts = {}) {
  showLoading(true);
  els.searchBtn.disabled = true;

  try {
    const resp = await fetch(`${API}/api/weather/full-by-coords?lat=${lat}&lon=${lon}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Location not found');
    }

    const data = await resp.json();
    state.weatherData = data;
    state.currentCity = data.city.name;

    renderDashboard(data);
    saveRecentSearch(data.city.name);

    els.welcomeState.style.display = 'none';
    els.dashboard.classList.add('visible');
    els.searchInput.value = data.city.name;

  } catch (err) {
    if (!opts.silent) showError(err.message || 'Failed to fetch weather data');
  } finally {
    showLoading(false);
    els.searchBtn.disabled = false;
  }
}

// ─── Render Dashboard ───────────────────────────
function renderDashboard(data) {
  const { city, current, forecast, historical, comparison, insight } = data;

  // Current weather
  els.currentTemp.textContent = formatTemp(current.temperature);
  els.currentFeels.textContent = `Feels like ${formatTemp(current.feels_like)}`;
  els.currentIcon.textContent = getEmoji(current.icon, current.is_day);
  els.currentCondition.textContent = current.condition;
  els.currentLocation.textContent = `${city.name}${city.admin1 ? ', ' + city.admin1 : ''}, ${city.country}`;

  // Details grid
  els.currentDetails.innerHTML = `
    <div class="detail-item">
      <span class="detail-icon">💧</span>
      <div><div class="detail-label">Humidity</div><div class="detail-value">${current.humidity}%</div></div>
    </div>
    <div class="detail-item">
      <span class="detail-icon">💨</span>
      <div><div class="detail-label">Wind</div><div class="detail-value">${current.wind_speed} km/h</div></div>
    </div>
    <div class="detail-item">
      <span class="detail-icon">🌧️</span>
      <div><div class="detail-label">Precipitation</div><div class="detail-value">${current.precipitation} mm</div></div>
    </div>
    <div class="detail-item">
      <span class="detail-icon">🌡️</span>
      <div><div class="detail-label">Pressure</div><div class="detail-value">${current.pressure} hPa</div></div>
    </div>
    <div class="detail-item">
      <span class="detail-icon">☁️</span>
      <div><div class="detail-label">Cloud Cover</div><div class="detail-value">${current.cloud_cover}%</div></div>
    </div>
    <div class="detail-item">
      <span class="detail-icon">🌬️</span>
      <div><div class="detail-label">Gusts</div><div class="detail-value">${current.wind_gusts || 0} km/h</div></div>
    </div>
  `;

  // Severity badge
  renderSeverityBadge(comparison);

  // Historical card
  renderHistorical(historical, comparison, current);

  // 24-hour hourly strip
  renderHourlyForecast(forecast);

  // Forecast strip
  renderForecast(forecast);

  // Charts
  renderTempChart(forecast);
  renderHistChart(historical);

  // Map
  renderMap(city);

  // AI Insight
  if (insight) {
    els.insightText.innerHTML = `<strong>${city.name}:</strong> ${insight}`;
    els.insightBanner.classList.add('visible');
  } else {
    els.insightBanner.classList.remove('visible');
  }
}

function renderSeverityBadge(comp) {
  if (!comp || comp.status) {
    els.severityBadge.textContent = 'N/A';
    els.severityBadge.className = 'card-badge badge-normal';
    return;
  }

  const sev = comp.severity || 'normal';
  const labels = {
    normal: 'Typical', mild: 'Slightly Unusual',
    moderate: 'Unusual', significant: 'Very Unusual', extreme: 'Extreme',
  };
  els.severityBadge.textContent = labels[sev] || sev;
  els.severityBadge.className = `card-badge badge-${sev}`;
}

function renderHistorical(hist, comp, current) {
  if (!hist || hist.error) {
    els.anomalyDesc.textContent = 'Historical data unavailable.';
    els.historicalStats.innerHTML = '';
    return;
  }

  // Trend badge
  const trend = hist.trend || {};
  const trendLabels = { warming: '🔺 Warming', cooling: '🔻 Cooling', stable: '➡️ Stable' };
  const trendColors = { warming: 'badge-significant', cooling: 'badge-mild', stable: 'badge-normal' };
  els.trendBadge.textContent = trendLabels[trend.direction] || 'Unknown';
  els.trendBadge.className = `card-badge ${trendColors[trend.direction] || 'badge-normal'}`;

  // Anomaly meter
  if (comp && !comp.status) {
    const t = hist.temperature;
    const range = t.record_high - t.record_low;
    let pct = range > 0 ? ((current.temperature - t.record_low) / range) * 100 : 50;
    pct = Math.max(2, Math.min(98, pct));
    els.anomalyFill.style.width = pct + '%';
    els.anomalyMarker.style.left = pct + '%';

    // Color fill based on severity
    const colors = {
      normal: 'var(--gradient-cool)',
      mild: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-amber))',
      moderate: 'linear-gradient(90deg, var(--accent-amber), var(--accent-orange))',
      significant: 'var(--gradient-warm)',
      extreme: 'linear-gradient(90deg, var(--accent-orange), var(--accent-rose))',
    };
    els.anomalyFill.style.background = colors[comp.severity] || colors.normal;

    els.anomalyDesc.textContent = comp.description;
    els.anomalyLow.textContent = `${t.record_low}°C`;
    els.anomalyHigh.textContent = `${t.record_high}°C`;
  }

  // Stats
  const t = hist.temperature;
  const p = hist.precipitation;
  els.historicalStats.innerHTML = `
    <div class="stat-item">
      <div class="stat-label">Mean Temp</div>
      <div class="stat-value">${t.mean}°C</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Std Deviation</div>
      <div class="stat-value">±${t.std_dev}°C</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Rainy Days</div>
      <div class="stat-value">${p.rainy_day_pct}%</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Trend Rate</div>
      <div class="stat-value">${trend.rate_per_year_c > 0 ? '+' : ''}${trend.rate_per_year_c}°C/yr</div>
    </div>
  `;
}

function renderHourlyForecast(fc) {
  if (!fc || !fc.hourly || fc.hourly.length === 0) {
    els.hourlyScroll.innerHTML = '';
    return;
  }

  // Take the next 24 hours
  const next24 = fc.hourly.slice(0, 24);

  els.hourlyScroll.innerHTML = next24.map((h, i) => {
    const d = new Date(h.time);
    const hour = d.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true });
    const label = i === 0 ? 'Now' : hour;

    return `
      <div class="hourly-card${i === 0 ? ' hourly-now' : ''}">
        <div class="hourly-time">${label}</div>
        <div class="hourly-icon">${getEmoji(h.icon)}</div>
        <div class="hourly-temp">${formatTemp(h.temperature)}</div>
        <div class="hourly-precip">💧 ${h.precip_probability || 0}%</div>
      </div>
    `;
  }).join('');
}

function renderForecast(fc) {
  if (!fc || !fc.daily) { els.forecastScroll.innerHTML = ''; return; }

  els.forecastScroll.innerHTML = fc.daily.map(d => `
    <div class="forecast-card">
      <div class="forecast-day">${dayName(d.date)}</div>
      <div class="forecast-icon">${getEmoji(d.icon)}</div>
      <div class="forecast-temps">
        <span class="forecast-high">${formatTemp(d.temp_max)}</span>
        <span class="forecast-low">${formatTemp(d.temp_min)}</span>
      </div>
      <div class="forecast-precip">💧 ${d.precip_probability || 0}%</div>
    </div>
  `).join('');
}

// ─── Charts ─────────────────────────────────────
const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } },
  },
  scales: {
    x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(148,163,184,0.08)' } },
    y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(148,163,184,0.08)' } },
  },
};

function renderTempChart(fc) {
  if (!fc || !fc.hourly) return;
  const ctx = $('tempChart');
  if (state.tempChart) state.tempChart.destroy();

  const labels = fc.hourly.map(h => {
    const d = new Date(h.time);
    return d.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true });
  });

  state.tempChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Temperature (°C)',
          data: fc.hourly.map(h => h.temperature),
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
        {
          label: 'Feels Like (°C)',
          data: fc.hourly.map(h => h.feels_like),
          borderColor: '#8b5cf6',
          borderDash: [4, 4],
          fill: false,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      ...chartDefaults,
      interaction: { mode: 'index', intersect: false },
    },
  });
}

function renderHistChart(hist) {
  if (!hist || !hist.yearly_breakdown || hist.yearly_breakdown.length === 0) return;
  const ctx = $('histChart');
  if (state.histChart) state.histChart.destroy();

  const years = hist.yearly_breakdown.map(y => y.year).reverse();
  const temps = hist.yearly_breakdown.map(y => y.avg_temp).reverse();
  const precip = hist.yearly_breakdown.map(y => y.total_precip).reverse();

  state.histChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: years,
      datasets: [
        {
          label: 'Avg Temp (°C)',
          data: temps,
          backgroundColor: 'rgba(59,130,246,0.6)',
          borderRadius: 4,
          yAxisID: 'y',
        },
        {
          label: 'Total Precip (mm)',
          data: precip,
          backgroundColor: 'rgba(6,182,212,0.4)',
          borderRadius: 4,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      ...chartDefaults,
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y, position: 'left', title: { display: true, text: '°C', color: '#64748b' } },
        y1: { ...chartDefaults.scales.y, position: 'right', title: { display: true, text: 'mm', color: '#64748b' }, grid: { drawOnChartArea: false } },
      },
    },
  });
}

// ─── Map ────────────────────────────────────────
function renderMap(city) {
  els.mapContainer.classList.add('visible');

  if (!state.map) {
    state.map = L.map('weather-map', {
      attributionControl: false,
      zoomControl: true,
    }).setView([city.latitude, city.longitude], 10);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
    }).addTo(state.map);

    // ── Interactive Map Click ──
    state.map.on('click', function (e) {
      const { lat, lng } = e.latlng;

      // Immediate visual feedback: place a pulsing temporary marker
      if (state.mapClickMarker) state.map.removeLayer(state.mapClickMarker);
      state.mapClickMarker = L.circleMarker([lat, lng], {
        radius: 10,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.5,
        weight: 2,
        className: 'map-click-pulse',
      }).addTo(state.map);

      // Fetch weather for clicked location
      searchByCoords(lat, lng);
    });
  } else {
    state.map.setView([city.latitude, city.longitude], 10);
  }

  // Remove temporary click marker
  if (state.mapClickMarker) {
    state.map.removeLayer(state.mapClickMarker);
    state.mapClickMarker = null;
  }

  if (state.mapMarker) state.map.removeLayer(state.mapMarker);

  state.mapMarker = L.marker([city.latitude, city.longitude]).addTo(state.map);
  state.mapMarker.bindPopup(`<b>${city.name}</b><br>${city.country}`).openPopup();

  // Fix map rendering after display toggle
  setTimeout(() => state.map.invalidateSize(), 300);
}

// ─── Chat ───────────────────────────────────────
function toggleChat() {
  state.chatOpen = !state.chatOpen;
  els.chatPanel.classList.toggle('open', state.chatOpen);
  if (state.chatOpen) els.chatInput.focus();
}

async function sendChatMessage() {
  const msg = els.chatInput.value.trim();
  if (!msg) return;
  if (!state.currentCity) {
    showError('Please search for a city first before chatting.');
    return;
  }

  // Add user message
  appendChatMessage('user', msg);
  els.chatInput.value = '';
  els.chatSend.disabled = true;
  els.chatTyping.classList.add('visible');

  state.chatHistory.push({ role: 'user', content: msg });

  try {
    const resp = await fetch(`${API}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        city: state.currentCity,
        history: state.chatHistory.slice(-8),
      }),
    });

    const data = await resp.json();

    if (data.status === 'error' || !resp.ok) {
      appendChatMessage('assistant', data.answer || data.detail || 'Sorry, an error occurred.');
    } else {
      const sources = data.sources && data.sources.length
        ? `<div class="sources">📎 Sources: ${data.sources.join(', ')}</div>`
        : '';
      appendChatMessage('assistant', formatMarkdown(data.answer) + sources);
      state.chatHistory.push({ role: 'assistant', content: data.answer });
    }
  } catch (err) {
    appendChatMessage('assistant', 'Failed to reach the AI service. Please check the backend.');
  } finally {
    els.chatTyping.classList.remove('visible');
    els.chatSend.disabled = false;
  }
}

function appendChatMessage(role, html) {
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.innerHTML = html;
  els.chatMessages.appendChild(div);
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

function formatMarkdown(text) {
  // Basic markdown → HTML
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

// ─── Comparison ─────────────────────────────────
async function compareCities() {
  const c1 = els.compareCity1.value.trim();
  const c2 = els.compareCity2.value.trim();
  if (!c1 || !c2) { showError('Enter two cities to compare'); return; }

  showLoading(true);
  els.compareBtn.disabled = true;

  try {
    const resp = await fetch(`${API}/api/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city1: c1, city2: c2 }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Comparison failed');
    }

    const data = await resp.json();
    renderComparison(data);
  } catch (err) {
    showError(err.message);
  } finally {
    showLoading(false);
    els.compareBtn.disabled = false;
  }
}

function renderComparison(data) {
  const render = (d, key) => {
    const info = d[key].info;
    const cur = d[key].current;
    const comp = d[key].comparison;
    const hist = d[key].historical;

    const sev = comp?.severity || 'normal';
    const badgeClass = `badge-${sev}`;
    const labels = { normal: 'Typical', mild: 'Slightly Unusual', moderate: 'Unusual', significant: 'Very Unusual', extreme: 'Extreme' };

    return `
      <div class="compare-city-card">
        <div class="compare-city-name">${getEmoji(cur.icon, cur.is_day)} ${info.name}, ${info.country}</div>
        <div class="compare-temp">${formatTemp(cur.temperature)}</div>
        <div style="color:var(--text-secondary);margin-top:4px;">${cur.condition} · Feels ${formatTemp(cur.feels_like)}</div>
        <span class="card-badge ${badgeClass}" style="display:inline-block;margin-top:8px;">${labels[sev] || sev}</span>
        <div class="compare-details">
          <div class="stat-item"><div class="stat-label">Humidity</div><div class="stat-value">${cur.humidity}%</div></div>
          <div class="stat-item"><div class="stat-label">Wind</div><div class="stat-value">${cur.wind_speed} km/h</div></div>
          <div class="stat-item"><div class="stat-label">Hist. Mean</div><div class="stat-value">${hist?.temperature?.mean ?? '--'}°C</div></div>
          <div class="stat-item"><div class="stat-label">Deviation</div><div class="stat-value">${comp?.difference != null ? (comp.difference > 0 ? '+' : '') + comp.difference + '°C' : '--'}</div></div>
        </div>
        ${comp?.description ? `<div style="margin-top:12px;font-size:0.82rem;color:var(--text-secondary);line-height:1.4;">${comp.description}</div>` : ''}
      </div>
    `;
  };

  els.compareGrid.innerHTML = render(data, 'city1') + render(data, 'city2');
}

// ─── Mode Toggle ────────────────────────────────
function setMode(mode) {
  state.mode = mode;
  els.modeDashboard.classList.toggle('active', mode === 'dashboard');
  els.modeCompare.classList.toggle('active', mode === 'compare');

  if (mode === 'dashboard') {
    els.compareSection.classList.remove('visible');
    if (state.weatherData) {
      els.dashboard.classList.add('visible');
    } else {
      els.welcomeState.style.display = '';
    }
  } else {
    els.dashboard.classList.remove('visible');
    els.welcomeState.style.display = 'none';
    els.compareSection.classList.add('visible');
  }
}

// ─── Recent Searches ────────────────────────────
function saveRecentSearch(city) {
  try {
    let recent = JSON.parse(localStorage.getItem('wt_recent') || '[]');
    recent = recent.filter(c => c.toLowerCase() !== city.toLowerCase());
    recent.unshift(city);
    localStorage.setItem('wt_recent', JSON.stringify(recent.slice(0, 8)));
  } catch { }
}

// ─── Event Listeners ────────────────────────────
els.searchBtn.addEventListener('click', () => searchCity(els.searchInput.value));
els.searchInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') searchCity(els.searchInput.value);
});

// Quick city buttons
document.querySelectorAll('.quick-city').forEach(btn => {
  btn.addEventListener('click', () => {
    const city = btn.dataset.city;
    els.searchInput.value = city;
    searchCity(city);
  });
});

// Chat
els.chatToggle.addEventListener('click', toggleChat);
els.chatClose.addEventListener('click', toggleChat);
els.chatSend.addEventListener('click', sendChatMessage);
els.chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') sendChatMessage();
});

// Mode toggle
els.modeDashboard.addEventListener('click', () => setMode('dashboard'));
els.modeCompare.addEventListener('click', () => setMode('compare'));

// Compare
els.compareBtn.addEventListener('click', compareCities);
els.compareCity1.addEventListener('keydown', e => { if (e.key === 'Enter') compareCities(); });
els.compareCity2.addEventListener('keydown', e => { if (e.key === 'Enter') compareCities(); });

// My Location button
els.locationBtn.addEventListener('click', requestGeolocation);

// ─── Geolocation ────────────────────────────────
function requestGeolocation() {
  if (!navigator.geolocation) {
    showError('Geolocation is not supported by your browser.');
    return;
  }

  els.locationBtn.classList.add('locating');

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      els.locationBtn.classList.remove('locating');
      const { latitude, longitude } = pos.coords;
      searchByCoords(latitude, longitude);
    },
    (err) => {
      els.locationBtn.classList.remove('locating');
      const msgs = {
        1: 'Location access denied. Please allow location access in your browser settings.',
        2: 'Unable to determine your location.',
        3: 'Location request timed out. Please try again.',
      };
      showError(msgs[err.code] || 'Failed to get location.');
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
  );
}

// ─── Init ───────────────────────────────────────
console.log('🌤️ WeatherTwin loaded');

// Auto-detect location on first load
requestGeolocation();
