# Deployment — GitHub Pages

The Flask scrollytelling app in [`src/app.py`](../src/app.py) is published
to **GitHub Pages** as a single self-contained HTML page, alongside the
Quarto documentation site. No external host, no secrets, no Docker.

Final URL after the first successful run:

```
https://<github-user>.github.io/<repo-name>/app/
```

For this repo: <https://podsv-fs26-ad24.github.io/ad24-4-fancyproject/app/>

## How it works

GitHub Pages cannot run Python. But our Flask app only does
server-side work *once* per request (Pandas filtering, Gaussian blur,
JSON serialisation) and then ships a fully client-side page (Plotly.js
renders the embedded JSON; the GDP/Pop toggle is plain DOM). So we
**pre-render** that one HTML response at CI build time and treat it as
a static file:

```
CI runner
 ├── quarto render docs/        → docs/build/                  (the docs site)
 ├── python build_static.py     → docs/build/app/index.html    (the app)
 └── upload-pages-artifact      → both, in one Pages deploy
```

The trick is Flask's test client: it walks through the real route
handler in-process (no socket bound) and returns the rendered HTML
identical to what `flask run` would serve.

## Contents of this folder

| File | Purpose |
|---|---|
| [`build_static.py`](build_static.py) | Imports `src.app`, runs the test client once, writes `docs/build/app/index.html` |
| [`requirements-build.txt`](requirements-build.txt) | Minimal deps for the build step (Flask + pandas + numpy + scipy) |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | This file |

## One-time GitHub setup

1. Repo → *Settings → Pages*.
2. Source: **GitHub Actions**.
3. Push to `main`. The existing workflow renders Quarto, runs
   `build_static.py` and deploys everything.

No secrets to configure.

## Trade-offs to be aware of

* **Page size.** The embedded JSON (aridity grid ≈ 50 k points,
  meteorite finds ≈ 38 k points, density grid) blows the HTML up to
  roughly **8–12 MB**. First load on a slow connection takes a couple
  of seconds; cached loads are instant. If this becomes a problem we
  can move the JSON to separate `.json` files and fetch them
  asynchronously.
* **Snapshot, not live.** The page reflects the data that was on disk
  when `main` was last pushed. Re-running the data pipeline locally
  (`src/helpers/aggregate_master_from_dataset.py` etc.) and committing
  the updated `output_data/` CSVs triggers a re-deploy with fresh data.
* **No interaction state beyond Plotly.** The GDP/Pop toggle and all
  hover tooltips work exactly as in dev because they're 100 % browser
  side. Anything that would require a *new* round-trip to Python (e.g.
  a search or recompute) would have to be re-architected.

## Local rebuild

```bash
# render the Quarto site once so the target directory exists
cd docs && uv run quarto render && cd ..

# bake the app into docs/build/app/index.html
uv run python deployment/build_static.py

# inspect the result in any browser
open docs/build/app/index.html
```

(The `uv run` prefix uses the project's existing env, where Flask /
pandas / numpy / scipy are already installed via `pyproject.toml`.)
