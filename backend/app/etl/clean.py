"""
clean.py

Filters and cleans a raw Spotify Extended Streaming History DataFrame
down to the fields relevant for the discovery-journey feature.

Design note: takes a DataFrame as a parameter rather than reading from
disk itself, so it can be reused as-is once this becomes a real upload
feature in Phase 2.
"""

import pandas as pd


# Columns we don't need for the discovery-journey feature
COLUMNS_TO_DROP = [
    "platform",
    "conn_country",
    "ip_addr",
    "offline",
    "offline_timestamp",
    "incognito_mode",
    "episode_name",
    "episode_show_name",
    "spotify_episode_uri",
    "audiobook_title",
    "audiobook_uri",
    "audiobook_chapter_uri",
    "audiobook_chapter_title",
]


def clean_streaming_history(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a raw streaming history DataFrame.

    Steps:
        1. Filter to rows with a non-null spotify_track_uri (drops
           podcast/audiobook rows in one shot, since those fields are
           null for music plays).
        2. Drop columns not needed for the discovery-journey feature.

    Args:
        df: Raw DataFrame as returned by loader.load_streaming_history().

    Returns:
        A cleaned DataFrame with music-only rows and only relevant columns.
    """
    original_count = len(df)

    # Step 1: keep music rows only
    music_only = df[df["spotify_track_uri"].notna()].copy()
    print(f"Dropped {original_count - len(music_only)} non-music rows "
          f"(podcasts/audiobooks), {len(music_only)} music rows remain")

    # Step 2: drop irrelevant columns (only drop ones that actually exist,
    # in case Spotify's export schema shifts slightly)
    columns_present = [col for col in COLUMNS_TO_DROP if col in music_only.columns]
    cleaned = music_only.drop(columns=columns_present)

    print(f"Dropped columns: {columns_present}")
    print(f"Remaining columns: {cleaned.columns.tolist()}")

    return cleaned


if __name__ == "__main__":
    # Quick manual test when running this file directly, chained with loader
    from pathlib import Path
    from loader import load_streaming_history

    # Build path relative to this script's location, not the terminal's
    # current directory, so this works no matter where you run it from
    project_root = Path(__file__).resolve().parents[2]  # backend/
    data_folder = project_root / "data" / "raw"

    raw = load_streaming_history(str(data_folder))
    clean = clean_streaming_history(raw)
    print(clean.head())