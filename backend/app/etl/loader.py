"""
loader.py

Reads Spotify Extended Streaming History JSON files and combines them
into a single pandas DataFrame.

Design note: takes a folder path as a parameter rather than hardcoding
one, so this same function works for the local prototype now and for
the file-upload feature later (Phase 2) without a rewrite.
"""

from pathlib import Path
import pandas as pd


def load_streaming_history(folder_path: str, pattern: str = "Streaming_History_Audio_*.json") -> pd.DataFrame:
    """
    Load and combine all Extended Streaming History JSON files in a folder.

    Args:
        folder_path: Path to the folder containing the JSON export files.
        pattern: Glob pattern to match the files (default matches Spotify's
                 default naming, e.g. Streaming_History_Audio_2021.json).

    Returns:
        A single pandas DataFrame combining every matched file, with a
        reset index.

    Raises:
        FileNotFoundError: if no files match the pattern in the given folder.
    """
    folder = Path(folder_path)
    files = sorted(folder.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No files matching '{pattern}' found in {folder_path}"
        )

    dataframes = []
    for file in files:
        df = pd.read_json(file)
        dataframes.append(df)
        print(f"Loaded {file.name}: {len(df)} rows")

    combined = pd.concat(dataframes, ignore_index=True)
    print(f"Total combined rows: {len(combined)}")

    return combined


if __name__ == "__main__":
    # Quick manual test when running this file directly
    data = load_streaming_history("data/raw")
    print(data.head())
    print(data.columns.tolist())