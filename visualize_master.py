"""
visualize_master.py
-------------------
Flask web app that displays master.csv on an interactive Plotly
choropleth world map.  Hover shows all metrics per country.
Aridity Index is rendered as a pixel-level heatmap overlay from
aridity_grid.csv for spatial detail.

Usage:
    pip install flask plotly
    python visualize_master.py
    → opens http://127.0.0.1:5000 in the browser
"""

import json
import os
import webbrowser
from threading import Timer

import pandas as pd
from flask import Flask, render_template_string

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE = os.path.dirname(__file__)
MASTER_CSV = os.path.join(BASE, 'data_sanitized', 'master.csv')
ARIDITY_GRID_CSV = os.path.join(BASE, 'data_sanitized', 'aridity_grid.csv')

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template – uses Plotly.js directly
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Data Explorer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', sans-serif;
      background: #0f0f1a;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
      padding: 1.2rem 2rem;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    header h1 {
      font-size: 1.5rem;
      font-weight: 700;
      color: #e2e8f0;
    }
    header .badge {
      font-size: 0.75rem;
      background: rgba(96,165,250,0.15);
      color: #60a5fa;
      padding: 0.25rem 0.65rem;
      border-radius: 999px;
      border: 1px solid rgba(96,165,250,0.25);
    }
    .controls {
      background: #131325;
      padding: 0.8rem 2rem;
      display: flex;
      gap: 0.75rem;
      align-items: center;
      flex-wrap: wrap;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .controls label {
      font-size: 0.8rem;
      font-weight: 600;
      color: #94a3b8;
      letter-spacing: 0.02em;
    }
    .controls select {
      background: #1e1e3a;
      color: #e2e8f0;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      padding: 0.45rem 0.75rem;
      font-family: 'Inter', sans-serif;
      font-size: 0.85rem;
      cursor: pointer;
      transition: border-color 0.2s;
    }
    .controls select:hover { border-color: #60a5fa; }
    .controls select:focus { outline: none; border-color: #a78bfa; }
    #map {
      flex: 1;
      min-height: 0;
    }
    .stats-bar {
      background: #131325;
      padding: 0.6rem 2rem;
      display: flex;
      gap: 2rem;
      border-top: 1px solid rgba(255,255,255,0.06);
      font-size: 0.78rem;
      color: #64748b;
    }
    .stats-bar span { color: #60a5fa; font-weight: 600; }
  </style>
</head>
<body>
  <header>
    <h1>🌍 Data Explorer</h1>
    <div class="badge">{{ n_countries }} countries</div>
  </header>
  <div class="controls">
    <label for="metric">Colour by:</label>
    <select id="metric">
      <option value="aridity_heatmap">Aridity Index (Heatmap)</option>
      <option value="aridity_index">Aridity Index (Country avg)</option>
      <option value="population_density_2022">Population Density (2022)</option>
      <option value="gdp_per_capita_2024">GDP per Capita (2024)</option>
    </select>
  </div>
  <div id="map"></div>
  <div class="stats-bar">
    <div>Source: <span>master.csv + aridity_grid.csv</span></div>
    <div>Metrics: <span>Aridity · Pop. Density · GDP · Income Class</span></div>
  </div>

  <script>
    // ---- data injected from Flask ----
    const DATA = {{ data_json|safe }};
    const GRID = {{ grid_json|safe }};

    const METRIC_LABELS = {
      aridity_index:            'Aridity Index (avg)',
      population_density_2022:  'Pop. Density (ppl/km²)',
      gdp_per_capita_2024:      'GDP per Capita (USD)',
    };

    const SCALES = {
      aridity_index:            'YlGnBu',
      population_density_2022:  'GrOrRd',
      gdp_per_capita_2024:      'GrOrRd',
    };

    const CLAMPS = {
      aridity_index:            { zmin: 0, zmax: 2.5 },
      population_density_2022:  { zmin: 0, zmax: 500 },
      gdp_per_capita_2024:      { zmin: 0, zmax: 100000 },
    };

    const GEO_LAYOUT = {
      showframe:      false,
      showcoastlines: true,
      coastlinecolor: '#334155',
      showland:       true,
      landcolor:      '#1e1e3a',
      showocean:      true,
      oceancolor:     '#0f0f1a',
      showcountries:  true,
      countrycolor:   '#334155',
      showlakes:      true,
      lakecolor:      '#0f0f1a',
      projection:     { type: 'natural earth' },
      bgcolor:        '#0f0f1a',
    };

    function fmtNum(v, decimals) {
      if (v == null || isNaN(v)) return '—';
      return Number(v).toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      });
    }

    function buildHoverText(d) {
      return '<b style="font-size:14px">' + d.country_name + '</b>' +
             '<br>─────────────────────' +
             '<br><b>Code:</b> ' + d.country_code +
             '<br><b>Region:</b> ' + d.region +
             '<br><b>Income:</b> ' + d.income_group +
             '<br>─────────────────────' +
             '<br>🌡️ <b>Aridity:</b> '     + fmtNum(d.aridity_index, 4) +
             '<br>👥 <b>Pop. Density:</b> ' + fmtNum(d.population_density_2022, 2) + ' /km²' +
             '<br>💰 <b>GDP/cap:</b> $'     + fmtNum(d.gdp_per_capita_2024, 0);
    }

    // --- Aridity heatmap (pixel-level scattergeo) ---
    function renderHeatmap() {
      const trace = {
        type: 'scattergeo',
        lat:  GRID.map(p => p.lat),
        lon:  GRID.map(p => p.lon),
        mode: 'markers',
        marker: {
          size:        4,
          opacity:     0.7,
          color:       GRID.map(p => p.aridity_index),
          colorscale:  'YlGnBu',
          cmin:        0,
          cmax:        2.5,
          colorbar: {
            title: { text: 'Aridity Index', font: { color: '#94a3b8', size: 12 } },
            tickfont:    { color: '#94a3b8' },
            bgcolor:     '#131325',
            bordercolor: '#334155',
            len: 0.6,
          },
          line: { width: 0 },
        },
        hovertemplate:
          '<b>Aridity Index</b>: %{marker.color:.4f}' +
          '<br>Lat: %{lat:.2f}°  Lon: %{lon:.2f}°' +
          '<extra></extra>',
        hoverlabel: {
          bgcolor:     '#1e1e3a',
          bordercolor: '#60a5fa',
          font: { family: 'Inter, sans-serif', size: 13, color: '#e2e8f0' },
        },
      };

      const layout = {
        geo:            GEO_LAYOUT,
        paper_bgcolor:  '#0f0f1a',
        plot_bgcolor:   '#0f0f1a',
        font:           { family: 'Inter, sans-serif', color: '#e2e8f0' },
        margin:         { l: 0, r: 0, t: 10, b: 0 },
        height:         window.innerHeight - 160,
      };

      Plotly.react('map', [trace], layout, { responsive: true });
    }

    // --- Country-level choropleth ---
    function renderChoropleth(metric) {
      const values = DATA.map(d => d[metric]);
      const hoverTexts = DATA.map(d => buildHoverText(d));
      const clamp = CLAMPS[metric];

      const trace = {
        type: 'choropleth',
        locations:     DATA.map(d => d.country_code),
        z:             values,
        zmin:          clamp.zmin,
        zmax:          clamp.zmax,
        text:          hoverTexts,
        hoverinfo:     'text',
        hoverlabel: {
          bgcolor:     '#1e1e3a',
          bordercolor: '#60a5fa',
          font: { family: 'Inter, sans-serif', size: 13, color: '#e2e8f0' },
          align: 'left',
        },
        colorscale: SCALES[metric],
        colorbar: {
          title: { text: METRIC_LABELS[metric], font: { color: '#94a3b8', size: 12 } },
          tickfont:    { color: '#94a3b8' },
          bgcolor:     '#131325',
          bordercolor: '#334155',
          len: 0.6,
        },
        marker: {
          line: { color: '#334155', width: 0.5 },
        },
      };

      const layout = {
        geo:            GEO_LAYOUT,
        paper_bgcolor:  '#0f0f1a',
        plot_bgcolor:   '#0f0f1a',
        font:           { family: 'Inter, sans-serif', color: '#e2e8f0' },
        margin:         { l: 0, r: 0, t: 10, b: 0 },
        height:         window.innerHeight - 160,
      };

      Plotly.react('map', [trace], layout, { responsive: true });
    }

    // --- Render dispatcher ---
    function renderMap(metric) {
      if (metric === 'aridity_heatmap') {
        renderHeatmap();
      } else {
        renderChoropleth(metric);
      }
    }

    // initial render
    renderMap('aridity_heatmap');

    // dropdown switch
    document.getElementById('metric').addEventListener('change', function() {
      renderMap(this.value);
    });

    // resize
    window.addEventListener('resize', function() {
      renderMap(document.getElementById('metric').value);
    });
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    df = pd.read_csv(MASTER_CSV)

    # Load aridity grid (if available)
    grid = []
    if os.path.exists(ARIDITY_GRID_CSV):
        gdf = pd.read_csv(ARIDITY_GRID_CSV)
        grid = gdf.to_dict(orient='records')

    data_json = json.dumps(df.to_dict(orient='records'))
    grid_json = json.dumps(grid)

    return render_template_string(
        HTML_TEMPLATE,
        n_countries=len(df),
        data_json=data_json,
        grid_json=grid_json,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def open_browser():
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    print("Starting Data Explorer …")
    print("→  http://127.0.0.1:5000")
    Timer(1.5, open_browser).start()
    app.run(debug=False, port=5000)
