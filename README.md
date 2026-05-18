# The Meteorite Illusion: Exposing Human Bias in the Search for Cosmic Treasure

A data visualization project using Python, uv for environment and package management and Quarto for documentation.

To adapt to your individual project change `sample` to the respective project name in the commands below

Adapt the `LICENSE` as required.

This project explores global meteorite landings together with environmental and economic context per country. The NASA meteorite landings dataset is sanitised and enriched with estimated market prices (scraped from an online meteorite retailer), then combined with the CGIAR Global Aridity Index, World Bank population density, GDP per capita and income class. The results are presented as an interactive Plotly world map – a country-level choropleth plus a pixel-level aridity heatmap – served by a small Flask web app.

## Project Organisation
The visualization product development is organised according to the following process model:

![The visualization product development process](docs/pics/vizproductprocess.png)

Code and configurations used in the different project phases are stored in the correspoding subfolders. Documentation artefacts in the form of a Quarto project are provided in `docs`.

| Phase | Code folders | Documentation section | `docs`-File |
|:-------|:---|:---|:---|
| Project Understanding | -  | Project Charta | project_charta.qmd  |
| Data Acquisition and Exploration | `eda` | Data Report | data_report.qmd  |
| Visual Encoding and Design | `encoding-design`  | Visual Encoding and Design | viz_encoding_design.qmd  |
| Evaluation | `evaluation`  | Evaluation | evaluation.qmd  |
| Deployment | `deployment` | Deployment | deplyoment.qmd |


> To do: Adjust accoding to your specific project needs - ensure consistency with readme, documentation, etc.

> To do: add link to documentation website for convenience.


See section `Quarto Setup and Usage` for instructions on how to build and serve the documentation website using Quarto.

## Project Structure

```
.
├── data_acquisition/                     Raw, unmodified source data
│   ├── Meteorite_Landings_NASA.csv         NASA meteorite landings (raw)
│   ├── meteorite_prices.csv                Scraped meteorite prices (raw)
│   ├── meteorite_prices_src_urls.txt       Source URLs collected by the scraper
│   ├── GDP_Per_Capita_2024_worldbank_Data.csv
│   ├── API_EN.POP.DNST_DS2_en_csv_v2_1453/ World Bank population density + metadata
│   └── Global-AridityIndex_v3_annual/      CGIAR Global Aridity Index GeoTIFF
├── data_sanitized/                       Cleaned data (intermediate)
│   ├── Meteorite_Landings_NASA_sanitized.csv
│   └── meteorite_prices_sanitized.csv
├── output_data/                          Final, aggregated data for visualization
│   ├── Meteorite_Landings_NASA_with_prices.csv
│   ├── aggregated_master_data.csv
│   └── aridity_grid.csv
├── src/                                  Application and pipeline code
│   ├── visualize_master_data.py            Flask + Plotly world-map web app
│   └── helpers/
│       ├── meteorite_price_scraper.py      Scrapes meteorite prices (Playwright)
│       ├── predict_meteorite_prices.py     Estimates a price per NASA meteorite
│       ├── aggregate_master_from_dataset.py Merges the country-level sources
│       └── sanitizers/
│           ├── sanitizer_meteorite_landings.py
│           └── sanitizer_meteorite_prices.py
├── eda/                                  Exploratory data analysis
├── docs/                                 Quarto documentation project
└── deployment/, evaluation/              Process-phase artefacts
```

## Data Pipeline

The code in `src/` produces the data in `output_data/` from the raw sources
in `data_acquisition/` in two independent strands.

**Strand A – Meteorite prices**

1. `helpers/meteorite_price_scraper.py` scrapes an online retailer and writes
   `data_acquisition/meteorite_prices.csv` (+ the source-URL list).
2. `helpers/sanitizers/sanitizer_meteorite_landings.py` cleans
   `Meteorite_Landings_NASA.csv` → `data_sanitized/Meteorite_Landings_NASA_sanitized.csv`
   (drops unusable `recclass`, relict entries and zero-mass rows).
3. `helpers/sanitizers/sanitizer_meteorite_prices.py` cleans
   `meteorite_prices.csv` → `data_sanitized/meteorite_prices_sanitized.csv`
   (strips `$`/`g`, maps categories to valid `recclass` values).
4. `helpers/predict_meteorite_prices.py` builds a median price-per-gram model
   per category and writes
   `output_data/Meteorite_Landings_NASA_with_prices.csv`.

**Strand B – Country-level master data**

1. `helpers/aggregate_master_from_dataset.py` merges the Global Aridity Index,
   population density, income class and GDP per capita per country and writes
   `output_data/aggregated_master_data.csv` plus a pixel-level
   `output_data/aridity_grid.csv` for the heatmap.

**Visualization**

`visualize_master_data.py` reads `aggregated_master_data.csv` and
`aridity_grid.csv` and serves the interactive map at `http://127.0.0.1:5000`.

## Quick Start

Run all commands from the repository root with the project environment active
(see the uv section below). Steps 1–4 only need to be repeated when the raw
data changes; the generated files are already provided in `output_data/`.

```bash
# 0. one-time environment setup
uv sync

# 1. (optional) re-scrape meteorite prices  → data_acquisition/meteorite_prices.csv
#    Only if re-scraping: install the Playwright browser binary once
uv run playwright install chromium
uv run python src/helpers/meteorite_price_scraper.py

# 2. sanitise the raw datasets              → data_sanitized/*.csv
uv run python src/helpers/sanitizers/sanitizer_meteorite_landings.py
uv run python src/helpers/sanitizers/sanitizer_meteorite_prices.py

# 3. estimate prices per meteorite          → output_data/Meteorite_Landings_NASA_with_prices.csv
uv run python src/helpers/predict_meteorite_prices.py

# 4. aggregate the country-level sources    → output_data/aggregated_master_data.csv, aridity_grid.csv
uv run python src/helpers/aggregate_master_from_dataset.py

# 5. launch the interactive world map       → http://127.0.0.1:5000
uv run python src/visualize_master_data.py
```

| Step | Script | Input | Output |
|:--|:--|:--|:--|
| 1 | `meteorite_price_scraper.py` | online retailer | `data_acquisition/meteorite_prices.csv`, `meteorite_prices_src_urls.txt` |
| 2 | `sanitizer_meteorite_landings.py` | `data_acquisition/Meteorite_Landings_NASA.csv` | `data_sanitized/Meteorite_Landings_NASA_sanitized.csv` |
| 2 | `sanitizer_meteorite_prices.py` | `data_acquisition/meteorite_prices.csv` | `data_sanitized/meteorite_prices_sanitized.csv` |
| 3 | `predict_meteorite_prices.py` | `data_sanitized/*_sanitized.csv` | `output_data/Meteorite_Landings_NASA_with_prices.csv` |
| 4 | `aggregate_master_from_dataset.py` | aridity GeoTIFF, World Bank CSVs | `output_data/aggregated_master_data.csv`, `aridity_grid.csv` |
| 5 | `visualize_master_data.py` | `output_data/aggregated_master_data.csv`, `aridity_grid.csv` | interactive web map |

## Python Environment Setup and Management with uv
Make sure to have uv installed: https://docs.astral.sh/uv/getting-started/installation/

After cloning the repository,  create the python environment with all dependencies based on the `.python-version`, `pyproject.toml` and `uv.lock` files by running
```bash
uv sync
```

To add new dependencies, use
```bash
uv add <package>
```
which will add the package to `pyproject.toml` and update the `uv.lock` file. You can also specify a version, e.g. `uv add pandas==2.0.3`.

Remove packages with
```bash
uv remove <package>
```

Commit changes to `pyproject.toml` and `uv.lock` files into version control.

Run `uv sync` after pulling changes to update the local environment.

Whenever the python environment is used, make sure to prefix every command that uses python with `uv run`, e.g.
```bash
uv run python script.py
```

You can also run
```bash 
source .venv/bin/activate
```
to activate the project Python environment in a terminal session in order to avoid having to prefix every command.

## Runtime Configuration with Environment Variables
The environment variables are specified in a .env-File, which is never commited into version control, as it may contain secrets. The repo just contains the file `.env.template` to demonstrate how environment variables are specified.

You have to create a local copy of `.env.template` in the project root folder and the easiest is to just rename it to `.env`.

The content of the .env-file is then read by the pypi-dependency: `python-dotenv`. Usage:
```python
import os
from dotenv import load_dotenv
```

`load_dotenv` reads the .env-file and sets the environment variables:

```python
load_dotenv()
```

which can then be accessed (assuming the file contains a line `SAMPLE_VAR=<some value>`):

```python
os.environ['SAMPLE_VAR']
```

## Quarto Setup and Usage

### Setup Quarto

1. [Install Quarto](https://quarto.org/docs/get-started/)
2. Optional: [quarto-extension for VS Code](https://marketplace.visualstudio.com/items?itemName=quarto.quarto)
3. If working with svg files and pdf output you will need to install rsvg-convert:
    * On macOS: `brew install librsvg`
    * On Windows using chocolatey:
      * [Install chocolatey](https://chocolatey.org/install#individual)
      * [Install rsvg-convert](https://community.chocolatey.org/packages/rsvg-convert): `choco install rsvg-convert`

Source `*.qmd` and configuration files are in the `docs` folder. The Quarto project configuration is in `docs/_quarto.yml`.

With embedded python code chunks that perform computations, you need to make sure that the python environment is activated when rendering. This can be done by prefixing the render command with `uv run`, e.g.:
```bash
uv run quarto render docs
```

### Working on the Documentation

1. Make changes to the `.qmd` source files in the `docs` folder
2. Make sure the project Python environment is activated (see Python environment setup and management)
3. Preview locally: `quarto preview` from the `docs` folder
4. Build the documentation website: `uv run quarto render` from the `docs` folder. This renders to `docs/build`
5. Check the website locally by opening `docs/build/index.html` in a browser

### Deployment of the Documentation to GitHub Pages

The documentation website is deployed to GitHub Pages via a GitHub Actions workflow (`.github/workflows/publish.yml`). Every push to `main` triggers the workflow, which renders the Quarto project and deploys the result.

The setting `execute: freeze: auto` in `_quarto.yml` ensures that Python computations are only executed locally. Results are cached in `docs/_freeze` and checked into the repository, so the GitHub Actions runner does not need Python — it uses the pre-computed results.

#### Initial Setup (once)

1. In the GitHub repository settings, go to **Settings > Pages** and set the source to **GitHub Actions**
2. Render locally so that `_freeze` contains cached computation results:
   ```bash
   cd docs && uv run quarto render
   ```
3. Push the changes to `main`

The `_freeze` directory and the workflow file `.github/workflows/publish.yml` should already be tracked in the repository.


#### Publishing Updates

1. Build the website locally: `uv run quarto render` from the `docs` folder. This updates `docs/build` (gitignored) and `docs/_freeze` (checked in)
2. Check the website locally by opening `docs/build/index.html`
3. Commit and push all updated files (including `docs/_freeze`) to `main`. The GitHub Actions workflow will render and deploy the site automatically
