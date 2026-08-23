"""
loader.py

Reads Spotify Extended Streaming History JSON files and combines them
into a single pandas DataFrame.

Two entry points:
    - load_streaming_history(): reads from a folder on disk. Used by
      the local prototype scripts (backend/data/raw/).
    - load_streaming_history_from_bytes(): reads from in-memory bytes.
      Used by the Phase 2 upload endpoint — the raw file content never
      touches disk, per the privacy architecture.

Both return the same shape of DataFrame, so everything downstream
(clean.py, aggregate.py, insights.py, story.py) works identically
regardless of which one was used.
"""

import io
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


def load_streaming_history_from_bytes(file_contents: list) -> pd.DataFrame:
    """
    Combine Spotify Extended Streaming History JSON files given as raw
    bytes, rather than reading from disk. This is what the upload
    endpoint calls — the uploaded file content is read into memory by
    FastAPI, converted to (filename, bytes) tuples, and passed here.
    Nothing is ever written to disk.

    Args:
        file_contents: list of (filename, bytes) tuples.

    Returns:
        A single combined DataFrame, same shape as load_streaming_history().

    Raises:
        ValueError: if no files were provided, or a file can't be
            parsed as JSON (surfaced by the endpoint as a 400).
    """
    if not file_contents:
        raise ValueError("No files provided")

    dataframes = []
    for filename, content in file_contents:
        try:
            df = pd.read_json(io.BytesIO(content))
        except ValueError as e:
            raise ValueError(f"Could not parse '{filename}' as JSON: {e}")
        dataframes.append(df)
        print(f"Loaded {filename}: {len(df)} rows")

    combined = pd.concat(dataframes, ignore_index=True)
    print(f"Total combined rows: {len(combined)}")

    return combined


if __name__ == "__main__":
    # Quick manual test when running this file directly
    data = load_streaming_history("data/raw")
    print(data.head())
    print(data.columns.tolist())