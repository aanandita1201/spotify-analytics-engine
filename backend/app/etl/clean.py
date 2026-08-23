"""
clean.py

Filters and cleans a raw Spotify Extended Streaming History DataFrame
down to the fields relevant for analysis.

Design note: takes a DataFrame as a parameter rather than reading from
disk itself, so it can be reused as-is once this becomes a real upload
feature in Phase 2.

Timezone note: every timestamp in the Spotify export ('ts') is UTC.
Since there are no user accounts, we only learn the user's timezone at
upload time (an IANA string like "America/New_York" sent from the
browser). This module is the single place UTC -> local conversion
happens; everything downstream (aggregate.py, insights.py, story.py)
reads already-localized timestamps and never touches timezone again.
"""

import pandas as pd


# Columns we don't need for analysis. Also where PII-adjacent fields
# get stripped in-memory, per the privacy architecture: none of these
# are ever written to disk or the database.
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

# Columns that later behavioral-signal metrics depend on. If Spotify's
# export schema shifts and one of these goes missing, we want a loud
# failure at cleaning time, not a silent KeyError three modules later.
REQUIRED_BEHAVIORAL_COLUMNS = ["reason_end", "shuffle", "skipped"]

DEFAULT_TIMEZONE = "UTC"


def _localize_timestamps(df: pd.DataFrame, user_timezone: str) -> pd.DataFrame:
    """
    Convert the 'ts' column from UTC to the user's local timezone.

    Args:
        df: DataFrame with a 'ts' column of UTC timestamps (string or
            datetime, tz-naive or already UTC-aware).
        user_timezone: IANA timezone string (e.g. "America/New_York").
            Falls back to UTC if invalid or not provided, so a bad/
            missing browser value never breaks the pipeline.

    Returns:
        The same DataFrame with 'ts' converted to tz-aware local time.
    """
    ts = pd.to_datetime(df["ts"], utc=True)

    try:
        df = df.copy()
        df["ts"] = ts.dt.tz_convert(user_timezone)
    except Exception as e:
        print(f"Invalid timezone '{user_timezone}' ({e}), falling back to UTC")
        df = df.copy()
        df["ts"] = ts.dt.tz_convert("UTC")

    return df


def clean_streaming_history(
    df: pd.DataFrame, user_timezone: str = DEFAULT_TIMEZONE
) -> pd.DataFrame:
    """
    Clean a raw streaming history DataFrame.

    Steps:
        1. Filter to rows with a non-null spotify_track_uri (drops
           podcast/audiobook rows in one shot, since those fields are
           null for music plays).
        2. Drop columns not needed for analysis (including all
           PII-adjacent fields).
        3. Convert 'ts' from UTC to the user's local timezone.

    Args:
        df: Raw DataFrame as returned by loader.load_streaming_history().
        user_timezone: IANA timezone string from the browser at upload
            time. Optional — defaults to UTC if not provided.

    Returns:
        A cleaned, localized DataFrame with music-only rows and only
        relevant columns.
    """
    original_count = len(df)

    # Step 1: keep music rows only
    music_only = df[df["spotify_track_uri"].notna()].copy()
    print(f"Dropped {original_count - len(music_only)} non-music rows "
          f"(podcasts/audiobooks), {len(music_only)} music rows remain")

    # Step 2: drop irrelevant/PII-adjacent columns (only drop ones that
    # actually exist, in case Spotify's export schema shifts slightly)
    columns_present = [col for col in COLUMNS_TO_DROP if col in music_only.columns]
    cleaned = music_only.drop(columns=columns_present)

    missing_behavioral = [c for c in REQUIRED_BEHAVIORAL_COLUMNS if c not in cleaned.columns]
    if missing_behavioral:
        print(f"WARNING: expected behavioral columns missing from export: "
              f"{missing_behavioral}. Skip/shuffle/completion metrics will be affected.")

    # Step 3: localize timestamps
    cleaned = _localize_timestamps(cleaned, user_timezone)

    print(f"Dropped columns: {columns_present}")
    print(f"Remaining columns: {cleaned.columns.tolist()}")
    print(f"Timestamps localized to: {user_timezone}")

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
    clean = clean_streaming_history(raw, user_timezone="America/New_York")
    print(clean.head())
    print(clean["ts"].dtype)