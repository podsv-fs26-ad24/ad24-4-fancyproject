"""
visualize_master_data.py
------------------------
Flask web app that displays aggregated_master_data.csv on an interactive Plotly
choropleth world map.  Hover shows all metrics per country.
Aridity Index is rendered as a pixel-level heatmap overlay from
aridity_grid.csv for spatial detail.

Usage:
    pip install flask plotly
    python visualize_master_data.py
    → opens http://127.0.0.1:5000 in the browser
"""

import json
import os
import webbrowser
from pathlib import Path
from threading import Timer

import numpy as np
import pandas as pd
from flask import Flask, render_template_string
from scipy.ndimage import gaussian_filter

# ---------------------------------------------------------------------------
# Config – paths resolved from this file so the app runs from any CWD
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
MASTER_CSV = str(ROOT / 'output_data' / 'aggregated_master_data.csv')
ARIDITY_GRID_CSV = str(ROOT / 'output_data' / 'aridity_grid.csv')
METEORITES_CSV = str(
    ROOT / 'output_data'
    / 'Meteorite_Landings_NASA_sanitized_clean_coordinates.csv'
)

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
      <option value="meteorite_landings">Meteorite Discovery Gap (Heatmap)</option>
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
    const LANDING = {{ landing_density_json|safe }};
    const LANDING_CMAX = {{ landing_cmax }};

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

    // --- Meteorite Discovery Gap (land-only heatmap) ---
    // For each land pixel of the aridity grid we know how many meteorites
    // have been found in its 1°×1° cell. Assuming meteorites fall uniformly
    // per km², low-find areas (green) represent the largest "unfound
    // potential", and high-find areas (red) are the established hotspots.
    function renderMeteorites() {
      const text = LANDING.map(d => {
        const gap = d.count === 0
          ? '🟢 High unfound potential'
          : (d.count < 5
              ? '🟡 Moderate unfound potential'
              : '🔴 Established find hotspot');
        return '<b>Discovery Gap</b>' +
               '<br>─────────────────────' +
               '<br><b>Cell:</b> ' + Number(d.lat).toFixed(1) + '°, '
                                   + Number(d.lon).toFixed(1) + '°' +
               '<br><b>Finds in 1° cell:</b> ' + d.count +
               '<br>' + gap;
      });

      const trace = {
        type: 'scattergeo',
        lat:  LANDING.map(p => p.lat),
        lon:  LANDING.map(p => p.lon),
        mode: 'markers',
        marker: {
          // Large, soft circles painted on top of a Gaussian-blurred density
          // field (smoothing happens server-side). Big translucent dots blend
          // into a continuous heatmap surface with bloom around hot cells –
          // no visible squares, just a smooth gradient.
          size:        14,
          opacity:     0.55,
          color:       LANDING.map(p => p.density),
          // Aggressive multi-stop ramp:
          //  - Zero / near-zero cells stay deep, saturated green so the
          //    "unfound" regions really pop out of the map.
          //  - Any noticeable density crosses into yellow/orange quickly.
          //  - The top of the scale is reserved for the densest find areas.
          colorscale:  [
            [0.00, '#15803d'],   // deep vivid green – truly zero finds
            [0.05, '#65a30d'],   // light green – essentially zero
            [0.18, '#facc15'],   // bright yellow – small but real density
            [0.40, '#f97316'],   // orange – common find region
            [0.70, '#dc2626'],   // red – established find hotspot
            [1.00, '#7f1d1d'],   // deep red – top-tier hotspot
          ],
          cmin:        0,
          cmax:        LANDING_CMAX,
          colorbar: {
            title: { text: 'Found density (log)', font: { color: '#94a3b8', size: 12 } },
            tickfont:    { color: '#94a3b8' },
            bgcolor:     '#131325',
            bordercolor: '#334155',
            len: 0.6,
          },
          line: { width: 0 },
        },
        text: text,
        hoverinfo: 'text',
        hoverlabel: {
          bgcolor:     '#1e1e3a',
          bordercolor: '#10b981',
          font: { family: 'Inter, sans-serif', size: 13, color: '#e2e8f0' },
          align: 'left',
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
      } else if (metric === 'meteorite_landings') {
        renderMeteorites();
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

    # Land-only meteorite *find density* heatmap.
    #
    # We bin the cleaned NASA landings (no missing/zero coordinates) into a
    # global 1°×1° count grid (180 rows × 360 cols), then apply a Gaussian
    # blur so that hot cells "bleed" into their neighbours – this gives the
    # smooth heatmap bloom that distinguishes a real density surface from a
    # checkerboard of discrete squares. We then sample the blurred field
    # only on the land pixels of the aridity grid, so nothing is drawn over
    # the ocean. log1p compresses the heavy-tailed distribution (Antarctica
    # blue ice and a few desert hotspots dominate raw counts) so the
    # gradient is readable across the rest of the world.
    landing_density = []
    landing_cmax = 1.0
    if os.path.exists(METEORITES_CSV) and os.path.exists(ARIDITY_GRID_CSV):
        mdf = pd.read_csv(
            METEORITES_CSV,
            usecols=['reclat', 'reclong'],
        ).dropna()

        # 1° global count grid – rows = lat (-90..89), cols = lon (-180..179)
        lat_idx = np.clip(np.floor(mdf['reclat']).astype(int) + 90, 0, 179)
        lon_idx = np.clip(np.floor(mdf['reclong']).astype(int) + 180, 0, 359)
        counts = np.zeros((180, 360), dtype=np.float64)
        np.add.at(counts, (lat_idx.values, lon_idx.values), 1.0)

        # Gaussian blur ~2.5° kernel → adjacent cells inherit hotspot heat.
        blurred = gaussian_filter(counts, sigma=2.5, mode='constant')

        land = pd.read_csv(ARIDITY_GRID_CSV)
        # Drop ocean / no-data pixels (encoded as 0 in the aridity grid).
        land = land[land['aridity_index'] > 0].copy()
        li = np.clip(np.floor(land['lat']).astype(int) + 90, 0, 179)
        lj = np.clip(np.floor(land['lon']).astype(int) + 180, 0, 359)

        land['count'] = counts[li, lj].astype(int)
        land['smoothed'] = blurred[li, lj]
        land['density'] = np.log1p(land['smoothed']).round(3)

        # Clamp the colour scale aggressively – at the 80th percentile of
        # non-zero cells – so that established find regions (US, Europe,
        # Argentina, …) clearly reach the orange/red band instead of being
        # crushed against the green floor by Antarctica's extreme tail.
        non_zero = land.loc[land['smoothed'] > 0, 'density']
        if len(non_zero):
            landing_cmax = float(round(non_zero.quantile(0.80), 3))
        landing_cmax = max(landing_cmax, 0.5)

        landing_density = (
            land[['lat', 'lon', 'count', 'density']]
            .round({'lat': 3, 'lon': 3})
            .to_dict(orient='records')
        )

    data_json = json.dumps(df.to_dict(orient='records'))
    grid_json = json.dumps(grid)
    landing_density_json = json.dumps(landing_density)

    return render_template_string(
        HTML_TEMPLATE,
        n_countries=len(df),
        data_json=data_json,
        grid_json=grid_json,
        landing_density_json=landing_density_json,
        landing_cmax=landing_cmax,
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
