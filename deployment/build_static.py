"""
build_static.py
---------------
Bake src/app.py into a fully static, GitHub-Pages-deployable HTML page.

Why this works:
    The Flask app does all its real work (Pandas filtering, Gaussian
    blur, connected-component labelling, JSON serialisation) in a SINGLE
    route handler – and the resulting HTML page is then 100 % client-side
    (Plotly.js renders the embedded JSON, the GDP/Pop toggle is plain
    DOM, no XHRs back to the server). Run that route handler *once* via
    Flask's test client, capture the response body and ship it as a
    static file.

Output:
    docs/build/app/index.html — merges with the Quarto-rendered site so
    the existing GitHub Pages workflow publishes both in one artefact.
    Final URL: https://<user>.github.io/<repo>/app/

Usage:
    # locally:
    uv run python deployment/build_static.py
    # in CI: see .github/workflows/publish.yml
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Make `src.app` importable from anywhere.
sys.path.insert(0, str(ROOT))

# Imported after sys.path mutation – noqa silences the lint warning.
from src.app import app  # noqa: E402

OUTPUT_DIR = ROOT / 'docs' / 'build' / 'app'
OUTPUT_FILE = OUTPUT_DIR / 'index.html'


def build() -> Path:
    """Render the app once and write the resulting HTML to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Flask test client = a fully-isolated, in-process HTTP request.
    # It walks through the real route handler, runs all data prep
    # (pandas read, gaussian_filter, label/erosion, JSON dumps) and
    # returns the rendered HTML – identical to what `flask run` would
    # serve, just without binding a socket.
    with app.test_client() as client:
        response = client.get('/')
        if response.status_code != 200:
            raise SystemExit(
                f"App returned HTTP {response.status_code} – aborting "
                f"static build. Body:\n{response.get_data(as_text=True)[:500]}"
            )
        html = response.get_data(as_text=True)

    OUTPUT_FILE.write_text(html, encoding='utf-8')
    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"[build_static] wrote {OUTPUT_FILE.relative_to(ROOT)} "
          f"({size_mb:,.2f} MB)")
    return OUTPUT_FILE


if __name__ == '__main__':
    build()
