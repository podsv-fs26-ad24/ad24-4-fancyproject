"""
aggregate_master.py
-------------------
Aggregates four source datasets into a single master.csv keyed by
country / region:

  1. Global Aridity Index  (GeoTIFF → country-level mean via lat/lon → country)
  2. Population density     (World Bank, 2022 column)
  3. Income class           (World Bank metadata)
  4. GDP per capita 2024    (World Bank)

The aridity GeoTIFF is heavily downsampled, then each pixel's lat/lon is
reverse-mapped to a country code with pycountry + reverse_geocoder so that
a per-country mean aridity index can be computed.

Because reverse-geocoding millions of pixels is expensive, we instead
compute a *country-level* aridity average by:
  - Downsampling the raster (factor 50 → ~manageable grid)
  - Using reverse_geocoder (offline, fast) to map each valid pixel to a
    country code
  - Grouping by country code and averaging

Output
------
  data_sanitized/master.csv   with columns:
    country_name, country_code, aridity_index, population_density_2022,
    income_group, gdp_per_capita_2024
"""

import os
import numpy as np
import pandas as pd

# Try to import rasterio & reverse_geocoder; they are optional heavy deps
try:
    import rasterio
    from rasterio.enums import Resampling
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

try:
    import reverse_geocoder as rg
    HAS_RG = True
except ImportError:
    HAS_RG = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = os.path.dirname(__file__)
DATA = os.path.join(BASE, 'data_acquisition')

ARIDITY_TIF = os.path.join(
    DATA, 'Global-AridityIndex_v3_annual', 'et0_v3_yr_sd.tif')

POP_DENSITY_CSV = os.path.join(
    DATA, 'API_EN.POP.DNST_DS2_en_csv_v2_1453',
    'API_EN.POP.DNST_DS2_en_csv_v2_1453.csv')

METADATA_CSV = os.path.join(
    DATA, 'API_EN.POP.DNST_DS2_en_csv_v2_1453',
    'Metadata_Country_API_EN.POP.DNST_DS2_en_csv_v2_1453.csv')

GDP_CSV = os.path.join(
    DATA, 'GDP_Per_Capita_2024_worldbank_Data.csv')

OUTPUT_DIR = os.path.join(BASE, 'data_sanitized')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'master.csv')

# ---------------------------------------------------------------------------
# 1.  Aridity Index  → country-level mean
# ---------------------------------------------------------------------------
DOWNSAMPLE_FACTOR = 50  # 50× smaller on each axis


def _load_aridity_by_country() -> pd.DataFrame:
    """
    Read the aridity GeoTIFF, downsample heavily, reverse-geocode every
    valid pixel to a country, and return a DataFrame with columns
    [country_code, aridity_index].
    """
    if not HAS_RASTERIO:
        print("[WARN] rasterio not installed – skipping aridity data.")
        return pd.DataFrame(columns=['country_code', 'aridity_index'])
    if not HAS_RG:
        print("[WARN] reverse_geocoder not installed – skipping aridity data.")
        return pd.DataFrame(columns=['country_code', 'aridity_index'])

    print("Reading aridity GeoTIFF (downsampled) …")
    with rasterio.open(ARIDITY_TIF) as src:
        out_h = src.height // DOWNSAMPLE_FACTOR
        out_w = src.width // DOWNSAMPLE_FACTOR
        data = src.read(
            1,
            out_shape=(out_h, out_w),
            resampling=Resampling.average,
        ).astype(np.float64)

        # Build a coordinate grid for the downsampled raster
        transform = src.transform * src.transform.scale(
            src.width / out_w, src.height / out_h)

    # NoData → NaN
    data[data < 0] = np.nan

    # Build (lat, lon) for every pixel
    rows, cols = np.where(~np.isnan(data))
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    lats = np.array(ys)  # y = latitude
    lons = np.array(xs)  # x = longitude
    # rasterio.transform.xy returns (x, y), i.e. (lon, lat)
    lats, lons = np.array(ys), np.array(xs)

    # Correct: rasterio.transform.xy returns (x=lon, y=lat) when given row,col
    # Actually it returns lists of x-coords and y-coords:
    # xs are longitudes, ys are latitudes... let's just look at the TFW:
    # line 5 = -179.99583  -> left lon
    # line 6 = 89.99583    -> top lat
    # So x = longitude, y = latitude. rasterio.transform.xy(transform, row, col)
    # returns (x, y) = (lon, lat).
    lons = np.array(xs)
    lats = np.array(ys)

    values = data[rows, cols]

    print(f"  {len(values):,} valid pixels – reverse-geocoding …")
    coords = list(zip(lats.tolist(), lons.tolist()))
    results = rg.search(coords)

    cc_list = [r['cc'] for r in results]

    df = pd.DataFrame({
        'country_code': cc_list,
        'aridity_value': values,
    })
    aridity = (
        df.groupby('country_code')['aridity_value']
        .mean()
        .reset_index()
        .rename(columns={'aridity_value': 'aridity_index'})
    )
    aridity['aridity_index'] = aridity['aridity_index'].round(2)
    print(f"  Aridity computed for {len(aridity)} countries.")
    return aridity


# ---------------------------------------------------------------------------
# 2.  Population density  → 2022 value per country
# ---------------------------------------------------------------------------
def _load_population_density() -> pd.DataFrame:
    """
    Read the World Bank population density CSV (skip first 4 meta rows)
    and extract the '2022' column.
    """
    print("Reading population density …")
    # The first 4 lines are metadata; actual header is line 5
    df = pd.read_csv(POP_DENSITY_CSV, skiprows=4)
    # Keep only country code + 2022 column
    if '2022' not in df.columns:
        print("[WARN] '2022' column not found in population density file.")
        return pd.DataFrame(columns=['country_code', 'population_density_2022'])

    out = df[['Country Code', '2022']].copy()
    out.columns = ['country_code', 'population_density_2022']
    out['population_density_2022'] = pd.to_numeric(
        out['population_density_2022'], errors='coerce').fillna(0)
    print(f"  {len(out)} entries loaded.")
    return out


# ---------------------------------------------------------------------------
# 3.  Income class per country
# ---------------------------------------------------------------------------
def _load_income_class() -> pd.DataFrame:
    """
    Read the World Bank metadata CSV and extract Country Code, IncomeGroup,
    Region, and TableName (= readable country name).
    """
    print("Reading income class metadata …")
    df = pd.read_csv(METADATA_CSV)
    out = df[['Country Code', 'IncomeGroup', 'Region', 'TableName']].copy()
    out.columns = ['country_code', 'income_group', 'region', 'country_name']
    out['income_group'] = out['income_group'].fillna('Unknown')
    out['region'] = out['region'].fillna('Unknown')
    out['country_name'] = out['country_name'].fillna('')
    print(f"  {len(out)} entries loaded.")
    return out


# ---------------------------------------------------------------------------
# 4.  GDP per capita 2024
# ---------------------------------------------------------------------------
def _load_gdp() -> pd.DataFrame:
    """
    Read GDP per capita (constant 2015 US$) for 2024 from the World Bank CSV.
    """
    print("Reading GDP per capita …")
    df = pd.read_csv(GDP_CSV)
    out = df[['Country Code', '2024 [YR2024]']].copy()
    out.columns = ['country_code', 'gdp_per_capita_2024']
    out['gdp_per_capita_2024'] = pd.to_numeric(
        out['gdp_per_capita_2024'].replace('..', np.nan), errors='coerce'
    ).fillna(0)
    print(f"  {len(out)} entries loaded.")
    return out


# ---------------------------------------------------------------------------
# 5.  ISO-3 ↔ ISO-2 mapping  (aridity uses 2-letter; World Bank uses 3-letter)
# ---------------------------------------------------------------------------
def _iso2_to_iso3_map() -> dict:
    """
    Return a dict mapping ISO-3166 alpha-2 → alpha-3.
    Uses pycountry if available, otherwise a hard-coded common subset.
    """
    try:
        import pycountry
        return {c.alpha_2: c.alpha_3 for c in pycountry.countries}
    except ImportError:
        print("[WARN] pycountry not installed – using built-in ISO map.")
        # Minimal fallback (extend as needed)
        return {
            'AF': 'AFG', 'AL': 'ALB', 'DZ': 'DZA', 'AD': 'AND', 'AO': 'AGO',
            'AG': 'ATG', 'AR': 'ARG', 'AM': 'ARM', 'AU': 'AUS', 'AT': 'AUT',
            'AZ': 'AZE', 'BS': 'BHS', 'BH': 'BHR', 'BD': 'BGD', 'BB': 'BRB',
            'BY': 'BLR', 'BE': 'BEL', 'BZ': 'BLZ', 'BJ': 'BEN', 'BT': 'BTN',
            'BO': 'BOL', 'BA': 'BIH', 'BW': 'BWA', 'BR': 'BRA', 'BN': 'BRN',
            'BG': 'BGR', 'BF': 'BFA', 'BI': 'BDI', 'KH': 'KHM', 'CM': 'CMR',
            'CA': 'CAN', 'CV': 'CPV', 'CF': 'CAF', 'TD': 'TCD', 'CL': 'CHL',
            'CN': 'CHN', 'CO': 'COL', 'KM': 'COM', 'CG': 'COG', 'CD': 'COD',
            'CR': 'CRI', 'CI': 'CIV', 'HR': 'HRV', 'CU': 'CUB', 'CY': 'CYP',
            'CZ': 'CZE', 'DK': 'DNK', 'DJ': 'DJI', 'DM': 'DMA', 'DO': 'DOM',
            'EC': 'ECU', 'EG': 'EGY', 'SV': 'SLV', 'GQ': 'GNQ', 'ER': 'ERI',
            'EE': 'EST', 'ET': 'ETH', 'FJ': 'FJI', 'FI': 'FIN', 'FR': 'FRA',
            'GA': 'GAB', 'GM': 'GMB', 'GE': 'GEO', 'DE': 'DEU', 'GH': 'GHA',
            'GR': 'GRC', 'GD': 'GRD', 'GT': 'GTM', 'GN': 'GIN', 'GW': 'GNB',
            'GY': 'GUY', 'HT': 'HTI', 'HN': 'HND', 'HU': 'HUN', 'IS': 'ISL',
            'IN': 'IND', 'ID': 'IDN', 'IR': 'IRN', 'IQ': 'IRQ', 'IE': 'IRL',
            'IL': 'ISR', 'IT': 'ITA', 'JM': 'JAM', 'JP': 'JPN', 'JO': 'JOR',
            'KZ': 'KAZ', 'KE': 'KEN', 'KI': 'KIR', 'KP': 'PRK', 'KR': 'KOR',
            'KW': 'KWT', 'KG': 'KGZ', 'LA': 'LAO', 'LV': 'LVA', 'LB': 'LBN',
            'LS': 'LSO', 'LR': 'LBR', 'LY': 'LBY', 'LI': 'LIE', 'LT': 'LTU',
            'LU': 'LUX', 'MG': 'MDG', 'MW': 'MWI', 'MY': 'MYS', 'MV': 'MDV',
            'ML': 'MLI', 'MT': 'MLT', 'MH': 'MHL', 'MR': 'MRT', 'MU': 'MUS',
            'MX': 'MEX', 'FM': 'FSM', 'MD': 'MDA', 'MC': 'MCO', 'MN': 'MNG',
            'ME': 'MNE', 'MA': 'MAR', 'MZ': 'MOZ', 'MM': 'MMR', 'NA': 'NAM',
            'NR': 'NRU', 'NP': 'NPL', 'NL': 'NLD', 'NZ': 'NZL', 'NI': 'NIC',
            'NE': 'NER', 'NG': 'NGA', 'NO': 'NOR', 'OM': 'OMN', 'PK': 'PAK',
            'PW': 'PLW', 'PA': 'PAN', 'PG': 'PNG', 'PY': 'PRY', 'PE': 'PER',
            'PH': 'PHL', 'PL': 'POL', 'PT': 'PRT', 'QA': 'QAT', 'RO': 'ROU',
            'RU': 'RUS', 'RW': 'RWA', 'KN': 'KNA', 'LC': 'LCA', 'VC': 'VCT',
            'WS': 'WSM', 'SM': 'SMR', 'ST': 'STP', 'SA': 'SAU', 'SN': 'SEN',
            'RS': 'SRB', 'SC': 'SYC', 'SL': 'SLE', 'SG': 'SGP', 'SK': 'SVK',
            'SI': 'SVN', 'SB': 'SLB', 'SO': 'SOM', 'ZA': 'ZAF', 'SS': 'SSD',
            'ES': 'ESP', 'LK': 'LKA', 'SD': 'SDN', 'SR': 'SUR', 'SZ': 'SWZ',
            'SE': 'SWE', 'CH': 'CHE', 'SY': 'SYR', 'TJ': 'TJK', 'TZ': 'TZA',
            'TH': 'THA', 'TL': 'TLS', 'TG': 'TGO', 'TO': 'TON', 'TT': 'TTO',
            'TN': 'TUN', 'TR': 'TUR', 'TM': 'TKM', 'TV': 'TUV', 'UG': 'UGA',
            'UA': 'UKR', 'AE': 'ARE', 'GB': 'GBR', 'US': 'USA', 'UY': 'URY',
            'UZ': 'UZB', 'VU': 'VUT', 'VE': 'VEN', 'VN': 'VNM', 'YE': 'YEM',
            'ZM': 'ZMB', 'ZW': 'ZWE',
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_master():
    """Merge all four sources into master.csv."""

    # --- Load individual datasets ---
    aridity_df = _load_aridity_by_country()
    pop_df     = _load_population_density()
    income_df  = _load_income_class()
    gdp_df     = _load_gdp()

    # --- Convert aridity ISO-2 codes → ISO-3 so they match World Bank ---
    if not aridity_df.empty:
        iso_map = _iso2_to_iso3_map()
        aridity_df['country_code'] = (
            aridity_df['country_code'].map(iso_map))
        aridity_df = aridity_df.dropna(subset=['country_code'])

    # --- Use income_df as the base (it has country_name + code) ---
    # Filter out aggregate/region rows (those with empty Region = non-country)
    countries = income_df[income_df['region'] != 'Unknown'].copy()

    # --- Merge ---
    master = countries.merge(pop_df, on='country_code', how='left')
    master = master.merge(gdp_df, on='country_code', how='left')
    master = master.merge(aridity_df, on='country_code', how='left')

    # Fill missing values with 0
    for col in ['population_density_2022', 'gdp_per_capita_2024', 'aridity_index']:
        if col in master.columns:
            master[col] = master[col].fillna(0)

    # Reorder columns
    col_order = [
        'country_name', 'country_code', 'region', 'income_group',
        'aridity_index', 'population_density_2022', 'gdp_per_capita_2024',
    ]
    col_order = [c for c in col_order if c in master.columns]
    master = master[col_order]

    master = master.sort_values('country_name').reset_index(drop=True)

    # --- Save ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    master.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅  master.csv saved → {OUTPUT_FILE}")
    print(f"   {len(master)} countries / regions")
    print(f"   Columns: {list(master.columns)}")
    print(master.head(10).to_string(index=False))

    return master


if __name__ == '__main__':
    build_master()
