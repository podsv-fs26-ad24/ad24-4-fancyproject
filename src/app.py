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
from scipy.ndimage import gaussian_filter, label as ndi_label, binary_erosion

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
PRICES_CSV = str(ROOT / 'data_sanitized' / 'meteorite_prices_sanitized.csv')

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    df = pd.read_csv(MASTER_CSV)

    # ----- Single filtered land grid (re-used everywhere) -------------
    # Read the raster ONCE, then apply three filters in sequence so the
    # display, the density grid and the treasure-zone calculation all
    # share exactly the same set of "real land" cells:
    #   1. drop ocean / no-data pixels (aridity_index == 0)
    #   2. drop tiny isolated land components (single-pixel specks,
    #      stray islands) via connected-component labelling on a 1° mask
    #   3. binary_erosion by 1 pixel → drop the outermost coastal ring.
    #      The source raster averages every pixel that touches water,
    #      so coastal cells carry artificially low aridity values that
    #      otherwise paint every continent's edge in fake hyper-arid red
    #      AND bias the treasure-zone calculation toward the coast.
    land_grid = pd.DataFrame()
    if os.path.exists(ARIDITY_GRID_CSV):
        raw = pd.read_csv(ARIDITY_GRID_CSV)
        raw = raw[raw['aridity_index'] > 0]

        MIN_BIN_COMPONENT = 4
        g_lat = np.clip(np.floor(raw['lat']).astype(int) + 90, 0, 179)
        g_lon = np.clip(np.floor(raw['lon']).astype(int) + 180, 0, 359)
        land_mask = np.zeros((180, 360), dtype=bool)
        land_mask[g_lat.values, g_lon.values] = True

        labels, _ = ndi_label(land_mask)
        sizes = np.bincount(labels.ravel())
        keep_label = sizes >= MIN_BIN_COMPONENT
        keep_label[0] = False
        keep_bin = keep_label[labels]
        # Coastal ring removal (1° erosion).
        keep_bin = keep_bin & binary_erosion(keep_bin, iterations=1)

        land_grid = raw[keep_bin[g_lat.values, g_lon.values]].copy()

    grid = land_grid.to_dict(orient='records') if len(land_grid) else []

    # ----- Meteorite finds (Sections 1 & 2 dots, Section 3 density) ----
    points = []
    landing_density = []
    treasure_zones = []
    landing_cmax = 1.0
    if os.path.exists(METEORITES_CSV) and len(land_grid):
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

        # Re-use the filtered land grid – inherits the coastal + speckle
        # filter, so neither density nor treasure zones can sit on a
        # bogus coastal pixel.
        land = land_grid.copy()
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

        # ----- Section 3 "Treasure Zones" -----------------------------
        # Cells that satisfy BOTH scientific criteria for an unexploited
        # meteorite-hunting ground.
        #   1. Aridity Index < 0.1   → hyper-arid / arid; iron-nickel
        #      meteorites are preserved for millennia, virtually no rust.
        #   2. Smoothed find count < 0.8 → essentially untouched by
        #      systematic discovery, even after Gaussian smoothing across
        #      the neighbouring cells.
        treasure_df = land[
            (land['aridity_index'] < 0.1) & (land['smoothed'] < 0.8)
        ].copy()
        treasure_zones = (
            treasure_df[['lat', 'lon', 'aridity_index', 'count', 'smoothed']]
                .round({'lat': 3, 'lon': 3,
                        'aridity_index': 4, 'smoothed': 3})
                .to_dict(orient='records')
        )

    # ----- Price calculator (epilog) ----------------------------------
    # Same logic as src/helpers/predict_meteorite_prices.py: build a
    # per-category median price-per-gram model from the sanitised
    # scraped catalogue, then expose three artefacts to the frontend:
    #   - prices_listings: ~250 catalogue entries for the name dropdown
    #   - price_model:     {category → median $/g}
    #   - categories:      sorted list of categories with price data
    prices_listings = []
    price_model = {}
    categories = []
    if os.path.exists(PRICES_CSV):
        pdf = pd.read_csv(PRICES_CSV, sep=';')
        valid = pdf.dropna(subset=['price', 'mass', 'category'])
        valid = valid[
            (valid['price'] > 0)
            & (valid['mass'] > 0)
            & (valid['category'] != 'Unknown')
        ].copy()

        prices_listings = (
            valid[['name', 'category', 'mass', 'price']]
                .round({'mass': 2, 'price': 2})
                .sort_values('name')
                .to_dict(orient='records')
        )

        valid['ppg'] = valid['price'] / valid['mass']
        price_model = (
            valid.groupby('category')['ppg']
                 .median()
                 .round(3)
                 .to_dict()
        )
        categories = sorted(price_model.keys())

    return render_template(
        'index.html',
        n_countries=len(df),
        n_points=len(points),
        data_json=json.dumps(df.to_dict(orient='records')),
        grid_json=json.dumps(grid),
        points_json=json.dumps(points),
        landing_density_json=json.dumps(landing_density),
        treasure_zones_json=json.dumps(treasure_zones),
        n_treasure=len(treasure_zones),
        landing_cmax=landing_cmax,
        prices_listings_json=json.dumps(prices_listings),
        price_model_json=json.dumps(price_model),
        categories_json=json.dumps(categories),
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
