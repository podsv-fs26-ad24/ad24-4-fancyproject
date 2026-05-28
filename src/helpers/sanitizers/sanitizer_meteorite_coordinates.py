import pandas as pd
from pathlib import Path

# Repository root, resolved from this file so the script runs from any CWD
ROOT = Path(__file__).resolve().parents[3]

INPUT_FILE = ROOT / 'data_sanitized' / 'Meteorite_Landings_NASA_sanitized.csv'
OUTPUT_FILE = (
    ROOT / 'output_data'
    / 'Meteorite_Landings_NASA_sanitized_clean_coordinates.csv'
)


def sanitize(input_path: Path, output_path: Path) -> pd.DataFrame:
    """
    Remove entries with missing or zero coordinates.

    Many records in the sanitised NASA dataset still carry ``reclat`` and/or
    ``reclong`` of exactly ``0`` (or missing), which collapses them onto the
    Null Island origin instead of their real location and is unusable for
    any geographic visualization. This script drops those rows and writes a
    coordinate-clean copy to the ``output_data`` folder.

    A row is removed if any of the following is true:
      * ``reclat`` is missing or equal to ``0``
      * ``reclong`` is missing or equal to ``0``

    Parameters
    ----------
    input_path : Path
        Path to the sanitised NASA CSV.
    output_path : Path
        Path where the coordinate-clean CSV will be written.

    Returns
    -------
    pd.DataFrame
        The coordinate-clean DataFrame.
    """
    df = pd.read_csv(input_path)
    initial_count = len(df)

    # Coerce to numeric so blank/non-numeric values become NaN and are removed.
    df['reclat'] = pd.to_numeric(df['reclat'], errors='coerce')
    df['reclong'] = pd.to_numeric(df['reclong'], errors='coerce')

    mask_remove = (
        df['reclat'].isna()
        | df['reclong'].isna()
        | (df['reclat'] == 0)
        | (df['reclong'] == 0)
    )

    df_clean = df[~mask_remove].reset_index(drop=True)
    removed_count = initial_count - len(df_clean)
    print(
        f"Coordinate sanitisation: {removed_count} entries removed out of "
        f"{initial_count} ({len(df_clean)} remaining)."
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(output_path, index=False)
    print(f"Coordinate-clean dataset saved to: {output_path}")

    return df_clean


if __name__ == '__main__':
    sanitize(INPUT_FILE, OUTPUT_FILE)
