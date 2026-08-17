"""
aggregate.py

Takes the cleaned streaming history DataFrame and computes the
Discovery Journey feature: top 10 artists by total listening time,
and per-artist stats (discovery date, entry-point song, most-played
song, top 10 songs, favorite album, and "became a fan" date).

Design note: takes a DataFrame as a parameter, same pattern as
loader.py and clean.py, so this slots into the Phase 2 upload
endpoint without rework.
"""

import pandas as pd

# Plays shorter than this are treated as accidental/skips and excluded
MIN_MS_PLAYED = 30_000  # 30 seconds

# Minimum plays in a week to count as "fan-level" listening
FAN_WEEKLY_THRESHOLD = 3

# Number of following weeks to check for sustained listening
SUSTAIN_WINDOW_WEEKS = 4

# Minimum number of weeks (within the sustain window) that must also
# meet this play count for the spike to count as "sustained"
SUSTAIN_MIN_PLAYS = 2
SUSTAIN_MIN_WEEKS_MET = 2


def filter_real_plays(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out plays shorter than MIN_MS_PLAYED (likely skips/accidents)."""
    real_plays = df[df["ms_played"] >= MIN_MS_PLAYED].copy()
    real_plays["ts"] = pd.to_datetime(real_plays["ts"])
    print(f"Filtered to {len(real_plays)} real plays "
          f"(>= {MIN_MS_PLAYED / 1000:.0f}s), from {len(df)} total")
    return real_plays


def get_top_artists(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """
    Rank artists by total ms_played and return the top n.

    Returns a DataFrame with columns: artist, total_ms_played.
    """
    artist_totals = (
        df.groupby("master_metadata_album_artist_name")["ms_played"]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
        .rename(columns={
            "master_metadata_album_artist_name": "artist",
            "ms_played": "total_ms_played",
        })
    )
    return artist_totals


def find_became_fan_date(artist_plays: pd.DataFrame):
    """
    Find the 'became a fan' date for one artist's plays using a
    weekly play-count threshold that must be sustained.

    Logic:
        1. Bucket plays into calendar weeks.
        2. Find the first week with >= FAN_WEEKLY_THRESHOLD plays.
        3. Confirm it's sustained: within the following
           SUSTAIN_WINDOW_WEEKS weeks, at least SUSTAIN_MIN_WEEKS_MET
           of them must also have >= SUSTAIN_MIN_PLAYS.
        4. If not sustained, keep looking at the next candidate week.

    Args:
        artist_plays: DataFrame of one artist's plays (already filtered
                       to real plays), must include a 'ts' column.

    Returns:
        Timestamp of the start of the qualifying week, or None if the
        artist never hits a sustained spike.
    """
    weekly_counts = (
        artist_plays.set_index("ts")
        .resample("W")
        .size()
    )

    weeks = weekly_counts.index
    counts = weekly_counts.values

    for i, count in enumerate(counts):
        if count >= FAN_WEEKLY_THRESHOLD:
            window = counts[i + 1: i + 1 + SUSTAIN_WINDOW_WEEKS]
            weeks_met = (window >= SUSTAIN_MIN_PLAYS).sum()
            if weeks_met >= SUSTAIN_MIN_WEEKS_MET:
                return weeks[i]

    return None  # never sustained a fan-level spike


def build_artist_profile(df: pd.DataFrame, artist_name: str) -> dict:
    """
    Build the full discovery-journey profile for one artist.

    Args:
        df: Filtered (real-plays-only) DataFrame for ALL artists.
        artist_name: The artist to build a profile for.

    Returns:
        A dict with discovery date, entry-point song, most-played song,
        top 10 songs, favorite album, and became-a-fan date.
    """
    artist_plays = df[df["master_metadata_album_artist_name"] == artist_name].sort_values("ts")

    # Discovery date + entry-point song = the very first play
    first_play = artist_plays.iloc[0]
    discovery_date = first_play["ts"]
    entry_point_song = first_play["master_metadata_track_name"]

    # Most-played song + top 10 songs, ranked by total ms_played
    song_totals = (
        artist_plays.groupby("master_metadata_track_name")["ms_played"]
        .sum()
        .sort_values(ascending=False)
    )
    most_played_song = song_totals.index[0]
    top_10_songs = song_totals.head(10).reset_index().rename(
        columns={"master_metadata_track_name": "song", "ms_played": "total_ms_played"}
    ).to_dict(orient="records")

    # Favorite album, ranked by total ms_played
    album_totals = (
        artist_plays.groupby("master_metadata_album_album_name")["ms_played"]
        .sum()
        .sort_values(ascending=False)
    )
    favorite_album = album_totals.index[0] if len(album_totals) > 0 else None

    # Became-a-fan date
    became_fan_date = find_became_fan_date(artist_plays)

    return {
        "artist": artist_name,
        "total_ms_played": int(artist_plays["ms_played"].sum()),
        "discovery_date": discovery_date,
        "entry_point_song": entry_point_song,
        "became_fan_date": became_fan_date,
        "most_played_song": most_played_song,
        "top_10_songs": top_10_songs,
        "favorite_album": favorite_album,
    }


def build_discovery_journey(df: pd.DataFrame, n_artists: int = 10) -> list:
    """
    Full pipeline: filter real plays, get top n artists, build a
    profile for each.

    Args:
        df: Cleaned DataFrame (output of clean.clean_streaming_history).
        n_artists: How many top artists to profile.

    Returns:
        A list of per-artist profile dicts, ordered by total_ms_played
        descending.
    """
    real_plays = filter_real_plays(df)
    top_artists = get_top_artists(real_plays, n=n_artists)

    profiles = []
    for artist_name in top_artists["artist"]:
        profile = build_artist_profile(real_plays, artist_name)
        profiles.append(profile)
        print(f"Built profile for {artist_name}: "
              f"discovered {profile['discovery_date'].date()}, "
              f"became a fan "
              f"{profile['became_fan_date'].date() if profile['became_fan_date'] is not None else 'never (no sustained spike)'}")

    return profiles


if __name__ == "__main__":
    from pathlib import Path
    from loader import load_streaming_history
    from clean import clean_streaming_history

    project_root = Path(__file__).resolve().parents[2]  # backend/
    data_folder = project_root / "data" / "raw"

    raw = load_streaming_history(str(data_folder))
    cleaned = clean_streaming_history(raw)
    journey = build_discovery_journey(cleaned)

    print("\n--- Top artist profile (most played) ---")
    print(journey[0])