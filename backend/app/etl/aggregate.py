"""
aggregate.py

Takes the cleaned streaming history DataFrame and computes baseline
aggregates: top artists, per-artist discovery timelines, entry-point
songs, obsession periods, top songs/albums.

Design note: takes a DataFrame as a parameter, same pattern as
loader.py and clean.py, so this slots into the Phase 2 upload
endpoint without rework.
"""

import pandas as pd

MIN_MS_PLAYED = 30_000
FAN_WEEKLY_THRESHOLD = 3
SUSTAIN_WINDOW_WEEKS = 4
SUSTAIN_MIN_PLAYS = 2
SUSTAIN_MIN_WEEKS_MET = 2


def filter_real_plays(df: pd.DataFrame) -> pd.DataFrame:
    real_plays = df[df["ms_played"] >= MIN_MS_PLAYED].copy()
    real_plays["ts"] = pd.to_datetime(real_plays["ts"])
    print(f"Filtered to {len(real_plays)} real plays "
          f"(>= {MIN_MS_PLAYED / 1000:.0f}s), from {len(df)} total")
    return real_plays


def get_top_artists(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
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
    weekly_counts = artist_plays.set_index("ts").resample("W").size()
    weeks = weekly_counts.index
    counts = weekly_counts.values

    for i, count in enumerate(counts):
        if count >= FAN_WEEKLY_THRESHOLD:
            window = counts[i + 1: i + 1 + SUSTAIN_WINDOW_WEEKS]
            weeks_met = (window >= SUSTAIN_MIN_PLAYS).sum()
            if weeks_met >= SUSTAIN_MIN_WEEKS_MET:
                return weeks[i]
    return None


def build_artist_profile(df: pd.DataFrame, artist_name: str) -> dict:
    artist_plays = df[df["master_metadata_album_artist_name"] == artist_name].sort_values("ts")
    first_play = artist_plays.iloc[0]
    discovery_date = first_play["ts"]
    entry_point_song = first_play["master_metadata_track_name"]

    song_totals = (
        artist_plays.groupby("master_metadata_track_name")["ms_played"]
        .sum().sort_values(ascending=False)
    )
    most_played_song = song_totals.index[0]
    top_10_songs = song_totals.head(10).reset_index().rename(
        columns={"master_metadata_track_name": "song", "ms_played": "total_ms_played"}
    ).to_dict(orient="records")

    album_totals = (
        artist_plays.groupby("master_metadata_album_album_name")["ms_played"]
        .sum().sort_values(ascending=False)
    )
    favorite_album = album_totals.index[0] if len(album_totals) > 0 else None
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


def get_top_songs(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """
    Rank songs (track + artist pair, since track names can collide
    across artists) by total ms_played, overall across the whole
    library. Returns columns: song, artist, total_ms_played.
    """
    song_totals = (
        df.groupby(["master_metadata_track_name", "master_metadata_album_artist_name"])["ms_played"]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
        .rename(columns={
            "master_metadata_track_name": "song",
            "master_metadata_album_artist_name": "artist",
            "ms_played": "total_ms_played",
        })
    )
    return song_totals


def get_top_album(df: pd.DataFrame):
    """Overall favorite album (by ms_played) across the whole library, or None."""
    album_totals = (
        df.groupby("master_metadata_album_album_name")["ms_played"]
        .sum()
        .sort_values(ascending=False)
    )
    if len(album_totals) == 0:
        return None
    return {"album": album_totals.index[0], "total_ms_played": int(album_totals.iloc[0])}


# Fraction of a track's max-observed duration required to count as a
# "complete listen." Not 100% exact match, to allow for tiny tracking
# jitter in Spotify's own logging.
COMPLETION_THRESHOLD = 0.95


def mark_complete_listens(df: pd.DataFrame, threshold: float = COMPLETION_THRESHOLD) -> pd.DataFrame:
    """
    Flags each play as a 'complete listen' using that track's own
    max-observed ms_played (across the whole export) as a duration
    proxy — the export has no true track-duration field.

    Deliberately runs on the FULL cleaned play log, not the >=30s
    'real plays' filter: a short song can legitimately be played to
    completion in under 30 seconds, and the 30s floor would unfairly
    exclude those from ever counting as a genuine full listen.

    Args:
        df: cleaned DataFrame (output of clean.clean_streaming_history()).
        threshold: fraction of max-observed duration required to count
            as complete.

    Returns:
        Copy of df with an added boolean 'is_complete' column.
    """
    flagged = df.copy()
    max_duration = flagged.groupby("spotify_track_uri")["ms_played"].transform("max")
    flagged["is_complete"] = flagged["ms_played"] >= (threshold * max_duration)
    return flagged


def get_top_artists_by_complete_listens(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """
    Rank artists by NUMBER of complete listens (not raw ms_played) —
    see module docstring rationale. Also returns the actual minutes
    of listening time represented by those complete listens, since
    the count itself isn't a user-facing unit.

    Returns:
        DataFrame with columns: artist, complete_listens, complete_minutes.
    """
    flagged = mark_complete_listens(df)
    complete_only = flagged[flagged["is_complete"]]

    result = (
        complete_only.groupby("master_metadata_album_artist_name")
        .agg(
            complete_listens=("ms_played", "size"),
            complete_ms_played=("ms_played", "sum"),
        )
        .sort_values("complete_listens", ascending=False)
        .head(n)
        .reset_index()
        .rename(columns={"master_metadata_album_artist_name": "artist"})
    )
    result["complete_minutes"] = (result["complete_ms_played"] / 1000 / 60).round(1)
    return result.drop(columns=["complete_ms_played"])

def get_top_songs_by_complete_listens(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """
    Rank songs by NUMBER of complete listens, not raw ms_played.
    Grouped by (track, artist) pair since track names can collide
    across different artists.

    Returns:
        DataFrame with columns: song, artist, complete_listens.
    """
    flagged = mark_complete_listens(df)
    complete_only = flagged[flagged["is_complete"]]

    return (
        complete_only.groupby(["master_metadata_track_name", "master_metadata_album_artist_name"])
        .size()
        .sort_values(ascending=False)
        .head(n)
        .reset_index(name="complete_listens")
        .rename(columns={
            "master_metadata_track_name": "song",
            "master_metadata_album_artist_name": "artist",
        })
    )


def build_discovery_journey(df: pd.DataFrame, n_artists: int = 10) -> list:
    real_plays = filter_real_plays(df)
    top_artists = get_top_artists(real_plays, n=n_artists)
    profiles = []
    for artist_name in top_artists["artist"]:
        profile = build_artist_profile(real_plays, artist_name)
        profiles.append(profile)
    return profiles