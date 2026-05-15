import pandas as pd
import numpy as np
import os

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.join(os.path.dirname(__file__), 'data_sanitized')
NASA_FILE = os.path.join(BASE_DIR, 'Meteorite_Landings_NASA_sanitized.csv')
PRICES_FILE = os.path.join(BASE_DIR, 'meteorite_prices_sanitized.csv')
OUTPUT_FILE = os.path.join('output_data', 'Meteorite_Landings_NASA_with_prices.csv')


def _build_price_model(prices_df: pd.DataFrame) -> dict:
    """
    Build a simple price-per-gram model for each category from the prices
    dataset.  For every category we compute the median price-per-gram so
    that outliers do not skew the result.

    Returns
    -------
    dict
        Mapping of category (recclass) -> price-per-gram (float).
    """
    # Only keep rows where both price and mass are valid and > 0
    valid = prices_df.dropna(subset=['price', 'mass'])
    valid = valid[(valid['price'] > 0) & (valid['mass'] > 0)].copy()

    valid['price_per_gram'] = valid['price'] / valid['mass']

    # Group by category and take the median price per gram
    model = valid.groupby('category')['price_per_gram'].median().to_dict()
    return model


def predict_prices(nasa_path: str, prices_path: str, output_path: str) -> pd.DataFrame:
    """
    Predict a price for every meteorite in the NASA dataset by matching
    its recclass to the category-based price-per-gram model derived from
    the prices dataset, then multiplying by the meteorite's mass.

    Entries whose recclass has no match in the price model, or whose mass
    is missing / zero, receive a predicted price of 0.

    Parameters
    ----------
    nasa_path : str
        Path to the sanitised NASA meteorite landings CSV.
    prices_path : str
        Path to the sanitised meteorite prices CSV (semicolon-separated).
    output_path : str
        Path where the enriched dataset will be written.

    Returns
    -------
    pd.DataFrame
        The NASA dataset with an added ``predicted_price`` column.
    """
    # Load datasets
    nasa_df = pd.read_csv(nasa_path)
    prices_df = pd.read_csv(prices_path, sep=';')

    # Build the price-per-gram model from the known prices
    price_model = _build_price_model(prices_df)

    print("Price-per-gram model (median $/g):")
    for cat, ppg in sorted(price_model.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat:30s}  ${ppg:>10.2f}/g")

    # Map each NASA entry's recclass to the price model
    nasa_df['price_per_gram'] = nasa_df['recclass'].map(price_model)

    # Compute predicted price = mass * price_per_gram
    # Where either value is missing or mass is 0, default to 0
    nasa_df['predicted_price'] = np.where(
        nasa_df['price_per_gram'].notna() & nasa_df['mass (g)'].notna() & (nasa_df['mass (g)'] > 0),
        (nasa_df['mass (g)'] * nasa_df['price_per_gram']).round(2),
        0.0,
    )

    # Drop the helper column
    nasa_df.drop(columns=['price_per_gram'], inplace=True)

    # Summary statistics
    total = len(nasa_df)
    priced = (nasa_df['predicted_price'] > 0).sum()
    print(f"\nPredicted prices for {priced} / {total} entries "
          f"({total - priced} entries set to $0).")

    # Save result
    nasa_df.to_csv(output_path, index=False)
    print(f"Output saved to: {output_path}")

    return nasa_df


if __name__ == '__main__':
    predict_prices(NASA_FILE, PRICES_FILE, OUTPUT_FILE)
