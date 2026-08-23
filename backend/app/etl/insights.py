"""
insights.py

Computes the full locked analysis suite on top of the cleaned,
localized streaming history DataFrame: time & rhythm, loyalty &
commitment, behavioral signals, and statistical framing.

Design note: same pattern as loader/clean/aggregate — takes a
DataFrame as a parameter, no disk I/O, so this slots into the Phase 2
upload endpoint without rework.

Assumes df has already been through clean.clean_streaming_history()
(music-only rows, PII columns dropped, 'ts' localized to the user's
timezone) and aggregate.filter_real_plays() (>= 30s plays only) before
being passed in here, EXCEPT where a function explicitly filters real
plays itself (most-skipped and shuffle metrics need the full play log,
including short/skipped plays, so those take the pre-filter df).
"""

import numpy as np
import pandas as pd

try:
    from .aggregate import filter_real_plays, get_top_artists
except ImportError:
    # Falls back to flat import when run as a standalone script
    # (e.g. `python insights.py` directly from the etl/ folder).
    from aggregate import filter_real_plays, get_top_artists

# --- Locked thresholds ---
SESSION_GAP_MINUTES = 60
COMEBACK_GAP_DAYS = 90  # ~3 months
NIGHT_HOURS = set(range(22, 24)) | set(range(0, 5))   # 10pm-5am
EARLY_HOURS = set(range(5, 9))                        # 5am-9am
SLOW_BURN_DAYS = 30       # time-to-10th-play >= this = slow burn
LOVE_AT_FIRST_LISTEN_DAYS = 7  # time-to-10th-play <= this = love at first listen

SEASON_BY_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "fall", 10: "fall", 11: "fall",
}


# ---------------------------------------------------------------------------
# Time & rhythm
# ---------------------------------------------------------------------------

def time_of_day_profile(real_plays: pd.DataFrame) -> dict:
    """Night owl / early bird profile from local listening hours."""
    hours = real_plays["ts"].dt.hour
    hour_histogram = hours.value_counts().reindex(range(24), fill_value=0).tolist()

    total = len(real_plays)
    night_pct = round(hours.isin(NIGHT_HOURS).sum() / total * 100, 1) if total else 0.0
    early_pct = round(hours.isin(EARLY_HOURS).sum() / total * 100, 1) if total else 0.0

    if night_pct >= early_pct and night_pct >= 25:
        profile = "night_owl"
    elif early_pct > night_pct and early_pct >= 25:
        profile = "early_bird"
    else:
        profile = "flexible"

    return {
        "profile": profile,
        "night_listening_pct": night_pct,
        "early_morning_listening_pct": early_pct,
        "hour_histogram": hour_histogram,  # index 0-23, count of plays per local hour
    }


def weekday_weekend_split(real_plays: pd.DataFrame) -> dict:
    """
    Ms played on weekdays vs weekends — both as raw totals/percentages
    AND as a per-day average, since raw totals are structurally biased
    toward weekdays (5 days vs 2 per week) regardless of actual habits.
    The per-day average is the number that reflects real behavior.
    """
    is_weekend = real_plays["ts"].dt.dayofweek >= 5
    weekday_ms = int(real_plays.loc[~is_weekend, "ms_played"].sum())
    weekend_ms = int(real_plays.loc[is_weekend, "ms_played"].sum())
    total_ms = weekday_ms + weekend_ms

    # Normalize by the number of distinct calendar days actually present
    # in each bucket, not a fixed 5/2 assumption, in case the export
    # doesn't span full weeks at the edges.
    dates = pd.Series(real_plays["ts"].dt.date)
    is_weekend_date = pd.to_datetime(dates).dt.dayofweek >= 5
    num_weekdays = int(dates[~is_weekend_date].nunique())
    num_weekend_days = int(dates[is_weekend_date].nunique())

    avg_weekday_ms = weekday_ms / num_weekdays if num_weekdays else 0
    avg_weekend_ms = weekend_ms / num_weekend_days if num_weekend_days else 0
    more_on = "weekends" if avg_weekend_ms > avg_weekday_ms else "weekdays"

    return {
        "weekday_ms_played": weekday_ms,
        "weekend_ms_played": weekend_ms,
        "weekday_pct": round(weekday_ms / total_ms * 100, 1) if total_ms else 0.0,
        "weekend_pct": round(weekend_ms / total_ms * 100, 1) if total_ms else 0.0,
        "avg_minutes_per_weekday": round(avg_weekday_ms / 1000 / 60, 1),
        "avg_minutes_per_weekend_day": round(avg_weekend_ms / 1000 / 60, 1),
        "more_listening_on": more_on,
    }


def seasonality_per_artist(real_plays: pd.DataFrame, n_artists: int = 10) -> list:
    """
    For each of the top n artists, find which season they're played
    most in. Season mapping assumes Northern Hemisphere.
    """
    top_artists = get_top_artists(real_plays, n=n_artists)["artist"]
    results = []

    for artist in top_artists:
        artist_plays = real_plays[real_plays["master_metadata_album_artist_name"] == artist].copy()
        artist_plays["season"] = artist_plays["ts"].dt.month.map(SEASON_BY_MONTH)
        season_totals = artist_plays.groupby("season")["ms_played"].sum().sort_values(ascending=False)

        results.append({
            "artist": artist,
            "peak_season": season_totals.index[0],
            "season_breakdown_ms": season_totals.to_dict(),
        })

    return results


def longest_listening_streak(real_plays: pd.DataFrame) -> dict:
    """Longest run of consecutive calendar days with at least one play."""
    listen_dates = pd.Series(sorted(real_plays["ts"].dt.date.unique()))
    if len(listen_dates) == 0:
        return {"streak_days": 0, "start_date": None, "end_date": None}

    day_gaps = listen_dates.diff().apply(lambda d: d.days if pd.notna(d) else 1)
    streak_id = (day_gaps != 1).cumsum()

    grouped = listen_dates.groupby(streak_id)
    best_streak_key = grouped.size().idxmax()
    best_streak_dates = grouped.get_group(best_streak_key)

    return {
        "streak_days": int(len(best_streak_dates)),
        "start_date": str(best_streak_dates.iloc[0]),
        "end_date": str(best_streak_dates.iloc[-1]),
    }


def longest_hiatus(real_plays: pd.DataFrame) -> dict:
    """Longest gap between two listening days, plus the comeback track."""
    sorted_plays = real_plays.sort_values("ts")
    listen_dates = pd.Series(sorted(sorted_plays["ts"].dt.date.unique()))

    if len(listen_dates) < 2:
        return {"hiatus_days": 0, "comeback_track": None, "comeback_date": None}

    gaps = listen_dates.diff().apply(lambda d: d.days if pd.notna(d) else 0)
    max_gap_idx = gaps.idxmax()
    hiatus_days = int(gaps.iloc[max_gap_idx])
    comeback_date = listen_dates.iloc[max_gap_idx]

    comeback_play = sorted_plays[sorted_plays["ts"].dt.date == comeback_date].iloc[0]

    return {
        "hiatus_days": hiatus_days,
        "comeback_date": str(comeback_date),
        "comeback_track": comeback_play["master_metadata_track_name"],
        "comeback_artist": comeback_play["master_metadata_album_artist_name"],
    }


# ---------------------------------------------------------------------------
# Loyalty & commitment
# ---------------------------------------------------------------------------

def comeback_artists(real_plays: pd.DataFrame, gap_days: int = COMEBACK_GAP_DAYS) -> list:
    """
    Artists with a listening gap of >= gap_days (default ~3 months)
    followed by a return. Returns one entry per qualifying gap.
    """
    results = []
    grouped = real_plays.sort_values("ts").groupby("master_metadata_album_artist_name")

    for artist, plays in grouped:
        dates = pd.Series(sorted(plays["ts"].dt.date.unique()))
        if len(dates) < 2:
            continue

        gaps = dates.diff().apply(lambda d: d.days if pd.notna(d) else 0)
        qualifying = gaps[gaps >= gap_days]

        for idx in qualifying.index:
            results.append({
                "artist": artist,
                "gap_days": int(gaps.iloc[idx]),
                "left_off_date": str(dates.iloc[idx - 1]),
                "returned_date": str(dates.iloc[idx]),
            })

    results.sort(key=lambda r: r["gap_days"], reverse=True)
    return results


def time_to_10th_play(real_plays: pd.DataFrame, min_plays: int = 10) -> list:
    """
    Days between first play and 10th play, per artist with >= min_plays
    real plays. Classifies each as slow_burn / love_at_first_listen /
    steady. Chosen over "discovery to fan" heuristics for interview
    defensibility — it's a plain, reproducible count.
    """
    results = []
    grouped = real_plays.sort_values("ts").groupby("master_metadata_album_artist_name")

    for artist, plays in grouped:
        if len(plays) < min_plays:
            continue

        first_play_ts = plays["ts"].iloc[0]
        tenth_play_ts = plays["ts"].iloc[min_plays - 1]
        days_to_10th = (tenth_play_ts - first_play_ts).days

        if days_to_10th <= LOVE_AT_FIRST_LISTEN_DAYS:
            classification = "love_at_first_listen"
        elif days_to_10th >= SLOW_BURN_DAYS:
            classification = "slow_burn"
        else:
            classification = "steady"

        results.append({
            "artist": artist,
            "days_to_10th_play": days_to_10th,
            "classification": classification,
        })

    results.sort(key=lambda r: r["days_to_10th_play"])
    return results


def retention_curve(real_plays: pd.DataFrame) -> dict:
    """
    Distribution of artists by play-count bucket: one-and-done vs
    casual vs regular vs obsession.
    """
    play_counts = real_plays.groupby("master_metadata_album_artist_name").size()

    buckets = {
        "one_and_done": int((play_counts == 1).sum()),
        "casual_2_to_5": int(play_counts.between(2, 5).sum()),
        "regular_6_to_20": int(play_counts.between(6, 20).sum()),
        "obsession_21_plus": int((play_counts > 20).sum()),
    }
    return buckets


# ---------------------------------------------------------------------------
# Behavioral signals
# ---------------------------------------------------------------------------

def most_skipped_track(all_plays: pd.DataFrame) -> dict:
    """
    Most-skipped track, using the 'skipped' boolean and 'reason_end'.
    Takes the FULL play log (pre real-plays filter) since skips are
    often short plays that filter_real_plays would otherwise exclude.
    """
    if "skipped" not in all_plays.columns:
        return {"track": None, "artist": None, "skip_count": 0, "note": "skipped column not present in export"}

    skipped = all_plays[all_plays["skipped"] == True]  # noqa: E712
    if len(skipped) == 0:
        return {"track": None, "artist": None, "skip_count": 0}

    top = (
        skipped.groupby(["master_metadata_track_name", "master_metadata_album_artist_name"])
        .size()
        .sort_values(ascending=False)
        .head(1)
    )
    (track, artist), count = top.index[0], top.iloc[0]
    top_reason = skipped[skipped["master_metadata_track_name"] == track]["reason_end"].mode()

    return {
        "track": track,
        "artist": artist,
        "skip_count": int(count),
        "most_common_skip_reason": top_reason.iloc[0] if len(top_reason) else None,
    }


def on_repeat_detection(all_plays: pd.DataFrame) -> dict:
    """
    Longest run of consecutive identical track URIs (true on-repeat
    behavior, distinct from just being a favorite song).
    """
    sorted_plays = all_plays.sort_values("ts").reset_index(drop=True)
    uris = sorted_plays["spotify_track_uri"]

    is_new_run = (uris != uris.shift()).cumsum()
    run_lengths = sorted_plays.groupby(is_new_run).size()

    if run_lengths.empty or run_lengths.max() <= 1:
        return {"track": None, "artist": None, "repeat_count": 0}

    best_run_id = run_lengths.idxmax()
    run_rows = sorted_plays[is_new_run == best_run_id]

    return {
        "track": run_rows["master_metadata_track_name"].iloc[0],
        "artist": run_rows["master_metadata_album_artist_name"].iloc[0],
        "repeat_count": int(run_lengths.max()),
        "run_start": run_rows["ts"].iloc[0].isoformat(),
    }


def shuffle_vs_deliberate(all_plays: pd.DataFrame, n_artists: int = 10) -> dict:
    """Overall and per-top-artist shuffle rate."""
    if "shuffle" not in all_plays.columns:
        return {"overall_shuffle_pct": None, "per_artist": [], "note": "shuffle column not present in export"}

    overall_pct = round(all_plays["shuffle"].mean() * 100, 1)

    top_artists = get_top_artists(filter_real_plays(all_plays), n=n_artists)["artist"]
    per_artist = []
    for artist in top_artists:
        artist_plays = all_plays[all_plays["master_metadata_album_artist_name"] == artist]
        per_artist.append({
            "artist": artist,
            "shuffle_pct": round(artist_plays["shuffle"].mean() * 100, 1),
        })

    return {"overall_shuffle_pct": overall_pct, "per_artist": per_artist}


def completion_rate(real_plays: pd.DataFrame) -> dict:
    """
    Average completion rate using max-observed ms_played per track as
    a duration proxy (the export has no true track-duration field).
    """
    max_duration_per_track = real_plays.groupby("spotify_track_uri")["ms_played"].transform("max")
    completion = (real_plays["ms_played"] / max_duration_per_track).clip(upper=1.0)

    return {
        "average_completion_rate": round(float(completion.mean()), 3),
        "note": "duration proxy = max ms_played observed for that track across all plays",
    }


# ---------------------------------------------------------------------------
# Statistical framing
# ---------------------------------------------------------------------------

def gini_concentration(real_plays: pd.DataFrame) -> dict:
    """
    Gini coefficient of listening concentration across artists.
    0 = perfectly even across all artists, 1 = all listening on one artist.
    """
    artist_totals = real_plays.groupby("master_metadata_album_artist_name")["ms_played"].sum()
    values = np.sort(artist_totals.values)
    n = len(values)

    if n == 0 or values.sum() == 0:
        return {"gini": 0.0}

    cumulative = np.cumsum(values)
    gini = (n + 1 - 2 * np.sum(cumulative) / cumulative[-1]) / n

    return {"gini": round(float(gini), 3), "n_artists": int(n)}


def total_listening_time(real_plays: pd.DataFrame) -> dict:
    """Headline stat: total time spent listening."""
    total_ms = int(real_plays["ms_played"].sum())
    return {
        "total_ms_played": total_ms,
        "total_hours": round(total_ms / 1000 / 60 / 60, 1),
        "total_days": round(total_ms / 1000 / 60 / 60 / 24, 2),
    }


def average_session_length(real_plays: pd.DataFrame, gap_minutes: int = SESSION_GAP_MINUTES) -> dict:
    """
    Sessionizes plays using a gap_minutes (default 60) break between
    plays to define a new session. Returns average session length in
    minutes and average tracks per session.
    """
    sorted_plays = real_plays.sort_values("ts").reset_index(drop=True)
    time_gaps = sorted_plays["ts"].diff()
    new_session = (time_gaps > pd.Timedelta(minutes=gap_minutes)) | time_gaps.isna()
    session_id = new_session.cumsum()

    sessions = sorted_plays.groupby(session_id).agg(
        start=("ts", "min"),
        end=("ts", "max"),
        track_count=("ts", "size"),
        ms_played=("ms_played", "sum"),
    )
    # Session wall-clock length = last track's start to first track's start,
    # plus the last track's own play time, so a single-track session isn't 0.
    sessions["duration_minutes"] = (
        (sessions["end"] - sessions["start"]).dt.total_seconds() / 60
    )

    return {
        "total_sessions": int(len(sessions)),
        "average_session_minutes": round(float(sessions["duration_minutes"].mean()), 1),
        "average_tracks_per_session": round(float(sessions["track_count"].mean()), 1),
    }


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def build_insights(cleaned_df: pd.DataFrame) -> dict:
    """
    Run the full locked analysis suite on a cleaned, localized
    streaming history DataFrame.

    Args:
        cleaned_df: output of clean.clean_streaming_history() — music
            only, PII stripped, 'ts' localized. NOT yet filtered to
            real plays (some metrics here need the full log).

    Returns:
        A dict keyed by category, matching the locked spec.
    """
    real_plays = filter_real_plays(cleaned_df)

    return {
        "time_and_rhythm": {
            "time_of_day_profile": time_of_day_profile(real_plays),
            "weekday_weekend_split": weekday_weekend_split(real_plays),
            "seasonality_per_artist": seasonality_per_artist(real_plays),
            "longest_streak": longest_listening_streak(real_plays),
            "longest_hiatus": longest_hiatus(real_plays),
        },
        "loyalty_and_commitment": {
            "comeback_artists": comeback_artists(real_plays),
            "time_to_10th_play": time_to_10th_play(real_plays),
            "retention_curve": retention_curve(real_plays),
        },
        "behavioral_signals": {
            "most_skipped_track": most_skipped_track(cleaned_df),
            "on_repeat": on_repeat_detection(cleaned_df),
            "shuffle_vs_deliberate": shuffle_vs_deliberate(cleaned_df),
            "completion_rate": completion_rate(real_plays),
        },
        "statistical_framing": {
            "gini_concentration": gini_concentration(real_plays),
            "total_listening_time": total_listening_time(real_plays),
            "average_session_length": average_session_length(real_plays),
        },
    }


if __name__ == "__main__":
    from pathlib import Path
    from loader import load_streaming_history
    from clean import clean_streaming_history

    project_root = Path(__file__).resolve().parents[2]  # backend/
    data_folder = project_root / "data" / "raw"

    raw = load_streaming_history(str(data_folder))
    cleaned = clean_streaming_history(raw, user_timezone="America/New_York")
    insights = build_insights(cleaned)

    import json
    print(json.dumps(insights, indent=2, default=str))