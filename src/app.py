"""
app.py
------
Scrollytelling Flask web app that tells the story of meteorites on Earth in
three acts.  Each act renders one of the three Plotly maps directly inside
its dedicated container, sharing the storytelling layout of index.html.

Server-side data preparation is preserved 1:1 from visualize_master_data.py:
the aridity grid (with land-only filter + connected-component speckle
removal), the Gaussian-blurred meteorite Discovery Gap density grid, the
country master frame and the cleaned meteorite-find coordinates.

Usage:
    uv run python src/app.py
    → opens http://127.0.0.1:5001 in the browser
"""

import json
import os
import webbrowser
from pathlib import Path
from threading import Timer

import numpy as np
import pandas as pd
from flask import Flask, render_template
from scipy.ndimage import gaussian_filter, label as ndi_label

# ---------------------------------------------------------------------------
# Config – paths resolved from this file so the app runs from any CWD
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = Path(__file__).resolve().parent / 'templates'

MASTER_CSV = str(ROOT / 'output_data' / 'aggregated_master_data.csv')
ARIDITY_GRID_CSV = str(ROOT / 'output_data' / 'aridity_grid.csv')
METEORITES_CSV = str(
    ROOT / 'output_data'
    / 'Meteorite_Landings_NASA_sanitized_clean_coordinates.csv'
)

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    df = pd.read_csv(MASTER_CSV)

    # ----- Aridity land grid (Section 3 base layer) --------------------
    # Drop ocean / no-data pixels (encoded as 0) AND remove isolated
    # speckles via connected-component labelling on a 1° land mask.
    grid = []
    if os.path.exists(ARIDITY_GRID_CSV):
        gdf = pd.read_csv(ARIDITY_GRID_CSV)
        gdf = gdf[gdf['aridity_index'] > 0]

        MIN_BIN_COMPONENT = 4
        g_lat_bin = np.clip(np.floor(gdf['lat']).astype(int) + 90, 0, 179)
        g_lon_bin = np.clip(np.floor(gdf['lon']).astype(int) + 180, 0, 359)
        land_mask = np.zeros((180, 360), dtype=np.int8)
        land_mask[g_lat_bin.values, g_lon_bin.values] = 1
        labels, _ = ndi_label(land_mask)
        sizes = np.bincount(labels.ravel())
        keep_label = sizes >= MIN_BIN_COMPONENT
        keep_label[0] = False
        keep_bin = keep_label[labels]
        gdf = gdf[keep_bin[g_lat_bin.values, g_lon_bin.values]]

        grid = gdf.to_dict(orient='records')

    # ----- Meteorite finds (Sections 1 & 2 dots, Section 3 density) ----
    points = []
    landing_density = []
    landing_cmax = 1.0
    if os.path.exists(METEORITES_CSV) and os.path.exists(ARIDITY_GRID_CSV):
        mdf = pd.read_csv(
            METEORITES_CSV, usecols=['reclat', 'reclong']
        ).dropna()

        # Raw points for the dot layer (Sections 1 & 2). Lightweight
        # payload: just lat/lon, rounded to 3 decimals.
        points = (
            mdf.rename(columns={'reclat': 'lat', 'reclong': 'lon'})
               .round({'lat': 3, 'lon': 3})
               .to_dict(orient='records')
        )

        # Gaussian-blurred 1° density grid → Discovery Gap heatmap.
        lat_idx = np.clip(np.floor(mdf['reclat']).astype(int) + 90, 0, 179)
        lon_idx = np.clip(np.floor(mdf['reclong']).astype(int) + 180, 0, 359)
        counts = np.zeros((180, 360), dtype=np.float64)
        np.add.at(counts, (lat_idx.values, lon_idx.values), 1.0)
        blurred = gaussian_filter(counts, sigma=2.5, mode='constant')

        land = pd.read_csv(ARIDITY_GRID_CSV)
        land = land[land['aridity_index'] > 0].copy()
        li = np.clip(np.floor(land['lat']).astype(int) + 90, 0, 179)
        lj = np.clip(np.floor(land['lon']).astype(int) + 180, 0, 359)
        land['count'] = counts[li, lj].astype(int)
        land['smoothed'] = blurred[li, lj]
        land['density'] = np.log1p(land['smoothed']).round(3)

        non_zero = land.loc[land['smoothed'] > 0, 'density']
        if len(non_zero):
            landing_cmax = float(round(non_zero.quantile(0.80), 3))
        landing_cmax = max(landing_cmax, 0.5)

        landing_density = (
            land[['lat', 'lon', 'count', 'density']]
                .round({'lat': 3, 'lon': 3})
                .to_dict(orient='records')
        )

    return render_template(
        'index.html',
        n_countries=len(df),
        n_points=len(points),
        data_json=json.dumps(df.to_dict(orient='records')),
        grid_json=json.dumps(grid),
        points_json=json.dumps(points),
        landing_density_json=json.dumps(landing_density),
        landing_cmax=landing_cmax,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _open_browser():
    webbrowser.open('http://127.0.0.1:5001')


if __name__ == '__main__':
    print("Starting Meteorite Storytelling app …")
    print("→  http://127.0.0.1:5001")
    Timer(1.5, _open_browser).start()
    app.run(debug=False, port=5001)
