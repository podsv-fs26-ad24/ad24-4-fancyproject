import pandas as pd
import re
import os

# Define file paths
INPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'Meteorite_Landings_NASA.csv')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'Meteorite_Landings_NASA_sanitized.csv')

# Characters that are not allowed in the recclass column
INVALID_RECCLASS_CHARS = re.compile(r'[/?()\~]')


def sanitize(input_path: str, output_path: str) -> pd.DataFrame:
    """
    Sanitize the meteorite landings dataset by removing unusable entries.

    Rules:
      1. Remove entries where 'recclass' contains any of: / ? ( ) ~
      2. Remove entries where 'recclass' is "Unknown" or empty
      3. Remove entries where 'nametype' is "Relict"
      4. Remove entries where 'mass (g)' is empty or 0

    Parameters
    ----------
    input_path : str
        Path to the raw CSV file.
    output_path : str
        Path where the sanitized CSV will be written.

    Returns
    -------
    pd.DataFrame
        The sanitized DataFrame.
    """
    df = pd.read_csv(input_path)

    initial_count = len(df)

    # Rule 1 & 2: Filter recclass column
    # Remove rows where recclass contains invalid characters
    mask_invalid_chars = df['recclass'].astype(str).apply(lambda x: bool(INVALID_RECCLASS_CHARS.search(x)))
    # Remove rows where recclass is "Unknown"
    mask_unknown = df['recclass'].astype(str).str.strip() == 'Unknown'
    # Remove rows where recclass is empty / NaN
    mask_empty_recclass = df['recclass'].isna() | (df['recclass'].astype(str).str.strip() == '')

    # Rule 3: Remove entries with nametype "Relict"
    mask_relict = df['nametype'].astype(str).str.strip() == 'Relict'

    # Rule 4: Remove entries where mass (g) is empty or 0
    mask_empty_mass = df['mass (g)'].isna()
    mask_zero_mass = df['mass (g)'] == 0

    # Combine all masks – any True means the row should be removed
    mask_remove = (
        mask_invalid_chars
        | mask_unknown
        | mask_empty_recclass
        | mask_relict
        | mask_empty_mass
        | mask_zero_mass
    )

    df_clean = df[~mask_remove].reset_index(drop=True)

    removed_count = initial_count - len(df_clean)
    print(f"Sanitization complete: {removed_count} entries removed out of {initial_count} "
          f"({len(df_clean)} remaining).")

    # Write sanitized data to output CSV
    df_clean.to_csv(output_path, index=False)
    print(f"Sanitized dataset saved to: {output_path}")

    return df_clean


if __name__ == '__main__':
    sanitize(INPUT_FILE, OUTPUT_FILE)
