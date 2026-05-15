import pandas as pd
import os

# Define file paths
INPUT_FILE = os.path.join(os.path.dirname(__file__), 'data_aquisition/meteorite_prices.csv')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'data_sanitized/meteorite_prices_sanitized.csv')

# Mapping from the prices dataset category names to the valid recclass values
# found in Meteorite_Landings_NASA_sanitized.csv.
# Categories that cannot be mapped to a valid recclass are set to None and will be removed.
CATEGORY_TO_RECCLASS = {
    'Campo del Cielo Iron Meteorite': 'Iron, IAB-MG',
    'Laâyoune 002 Lunar Meteorite': 'Lunar',
    'Clarendon (c) L4 Meteorite': 'L4',
    'Tassédet 004 H5 Impact Melt Meteorite': 'H5',
    'Gold Basin L4 Meteorite': 'L4',
    'NWA 869 L3-6 Meteorite': 'L3-6',
    'Sericho Pallasite Meteorite': 'Pallasite, PMG',
    'Muonionalusta Meteorite': 'Iron, IVA',
    'NWA 11700 H4 Meteorite': 'H4',
    'Dronino Ataxite Iron Meteorite': 'Iron, ungrouped',
    'Gebel Kamil Iron Meteorite': 'Iron, ungrouped',
    'NWA 10256 CR2 Meteorite': 'CR2',
    'Seymchan Siderite Meteorite': 'Iron, IIE-an',
    'Seymchan Pallasite Meteorite': 'Pallasite, PMG',
    'NWA 11788 Lunar Meteorite': 'Lunar',
    'NWA 12925 CK5 Meteorite': 'CK5',
    'Bechar 003 Lunar Meteorite': 'Lunar',
    'NWA 16315 Lunar Meteorite': 'Lunar',
    'Aguas Zarcas CM2 Meteorite': 'CM2',
    'Ajdabiya 001 Lunar Melt Breccia Meteorite': 'Lunar',
    'Aletai Meteorite': 'Iron, IIIAB',
    'Sikhote-Alin Iron Meteorite': 'Iron, IIAB',
    'NWA 13974 Lunar Meteorite': 'Lunar',
    'Dalgety Downs L4 Meteorite': 'L4',
    # Categories that do not correspond to a valid meteorite recclass
    'Saffordite': 'Unknown',
    'Meteorite Gifts': 'Unknown',
}


def sanitize(input_path: str, output_path: str) -> pd.DataFrame:
    """
    Sanitize the meteorite prices dataset.

    Steps:
      1. Remove '$' signs from the price column.
      2. Map the category column to valid recclass values from the
         Meteorite_Landings_NASA_sanitized dataset.
      3. Assign 'Unknown' to entries whose category cannot be mapped to a valid recclass.

    Parameters
    ----------
    input_path : str
        Path to the raw CSV file (semicolon-separated).
    output_path : str
        Path where the sanitized CSV will be written.

    Returns
    -------
    pd.DataFrame
        The sanitized DataFrame.
    """
    df = pd.read_csv(input_path, sep=';')

    initial_count = len(df)

    # Step 1: Remove '$' from the price column and convert to float
    df['price'] = df['price'].astype(str).str.replace('$', '', regex=False)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')

    # Step 2: Remove 'g' suffix from the mass column and convert to float
    df['mass'] = df['mass'].astype(str).str.replace('g', '', regex=False)
    df['mass'] = pd.to_numeric(df['mass'], errors='coerce')

    # Step 3: Map categories to valid recclass values, default to 'Unknown'
    df['category'] = df['category'].map(CATEGORY_TO_RECCLASS).fillna('Unknown')

    removed_count = initial_count - len(df)
    print(f"Sanitization complete: {removed_count} entries removed out of {initial_count} "
          f"({len(df)} remaining).")

    # Write sanitized data to output CSV
    df.to_csv(output_path, index=False, sep=';')
    print(f"Sanitized dataset saved to: {output_path}")

    return df


if __name__ == '__main__':
    sanitize(INPUT_FILE, OUTPUT_FILE)
