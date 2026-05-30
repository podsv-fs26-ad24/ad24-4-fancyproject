"""
app.py
------
Scrollytelling Flask web app that tells the story of meteorites on Earth in
three acts.  Each act has a placeholder container for one of the existing
maps (Aridity / Population & GDP combined / Meteorite Discovery Gap) and an
in-depth, journalistic German narrative.

The app intentionally serves only the storytelling shell – the individual
maps are dropped into their placeholder containers by the team (either via
iframe to the existing Flask visualiser, or as inline HTML / standalone
plotly snippets).

Usage:
    uv run python src/app.py
    → opens http://127.0.0.1:5001 in the browser
"""

import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, render_template

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = Path(__file__).resolve().parent / 'templates'

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    """Serve the single-page scrollytelling story."""
    return render_template('index.html')


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
