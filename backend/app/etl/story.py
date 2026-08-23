"""
story.py

Takes a cleaned, localized streaming history DataFrame and shapes it
into the final "story JSON" — a flat list of shareable_cards that the
frontend renders directly. Each card is either:

    {"id": ..., "type": "stat", "category": ..., "title": ...,
     "value": ..., "subtitle": ...}

or:

    {"id": ..., "type": "list", "category": ..., "title": ...,
     "items": [...], "subtitle": ...}

No visual-mapping fields (size, color, position) live here by design —
that's frontend-layer logic. Mixtape cards (top-10-as-playlist,
seasonal mixtapes) are explicitly out of scope for this version.

Field naming note: "first_streamed_date" / "obsession_period_start"
(not "discovery_date" / "became_fan_date") because the data can only
ever reflect Spotify streaming behavior — not when someone actually
first heard an artist or how they felt about them.
"""

from datetime import datetime, timezone
import pandas as pd

try:
    from .aggregate import (
        filter_real_plays,
        get_top_artists_by_complete_listens,
        get_top_songs_by_complete_listens,
        get_top_album,
        build_artist_profile,
    )
    from .insights import build_insights
except ImportError:
    # Falls back to flat imports when run as a standalone script
    # (e.g. `python story.py` directly from the etl/ folder).
    from aggregate import (
        filter_real_plays,
        get_top_artists_by_complete_listens,
        get_top_songs_by_complete_listens,
        get_top_album,
        build_artist_profile,
    )
    from insights import build_insights

DISCLAIMER = (
    "These stats reflect your Spotify streaming history only — not "
    "necessarily when you first heard an artist, how you actually felt "
    "about them, or what you listened to outside Spotify."
)


def _serialize(value):
    """Make pandas/NumPy/Timestamp values JSON-safe."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):  # numpy scalar (int64, float64, bool_)
        return value.item()
    return value


def _stat_card(card_id: str, category: str, title: str, value, subtitle: str = None) -> dict:
    return {
        "id": card_id,
        "type": "stat",
        "category": category,
        "title": title,
        "value": _serialize(value),
        "subtitle": subtitle,
    }


def _list_card(card_id: str, category: str, title: str, items: list, subtitle: str = None) -> dict:
    return {
        "id": card_id,
        "type": "list",
        "category": category,
        "title": title,
        "items": [{k: _serialize(v) for k, v in item.items()} for item in items],
        "subtitle": subtitle,
    }


def _baseline_cards(cleaned_df: pd.DataFrame, real_plays: pd.DataFrame) -> list:
    cards = []

    top_artists_df = get_top_artists_by_complete_listens(cleaned_df, n=10)
    cards.append(_list_card(
    "top_artists", "baseline", "Your Top Artists",
    top_artists_df[["artist", "complete_minutes"]].to_dict(orient="records"),
    subtitle="Ranked by complete listens, shown as minutes of full listens",
    )) 

    top_songs_df = get_top_songs_by_complete_listens(cleaned_df, n=10)
    cards.append(_list_card(
        "top_songs", "baseline", "Your Top Songs",
        top_songs_df.to_dict(orient="records"),
        subtitle="Ranked by complete listens — not total time played",
    ))

    top_artist_name = top_artists_df.iloc[0]["artist"]
    top_artist_profile = build_artist_profile(real_plays, top_artist_name)

    cards.append(_stat_card(
        "first_streamed_date", "baseline", "First Streamed",
        top_artist_profile["discovery_date"],
        subtitle=f"The day you first played {top_artist_name}",
    ))
    cards.append(_stat_card(
        "entry_point_song", "baseline", "Entry-Point Song",
        top_artist_profile["entry_point_song"],
        subtitle=f"The first {top_artist_name} song you played",
    ))
    cards.append(_stat_card(
        "obsession_period_start", "baseline", "Obsession Period Start",
        top_artist_profile["became_fan_date"],
        subtitle=f"When your {top_artist_name} listening became sustained",
    ))

    favorite_album = get_top_album(real_plays)
    if favorite_album:
        cards.append(_stat_card(
            "favorite_album", "baseline", "Favorite Album",
            favorite_album["album"],
        ))

    return cards


def _time_and_rhythm_cards(insights: dict) -> list:
    t = insights["time_and_rhythm"]
    cards = []

    profile = t["time_of_day_profile"]
    cards.append(_stat_card(
        "time_of_day_profile", "time_and_rhythm", "Night Owl or Early Bird?",
        profile["profile"],
        subtitle=f"{profile['night_listening_pct']}% night, {profile['early_morning_listening_pct']}% early morning",
    ))

    split = t["weekday_weekend_split"]
    cards.append(_stat_card(
        "weekday_weekend_split", "time_and_rhythm", "Weekday vs Weekend",
        f"You listen more on {split['more_listening_on']}",
        subtitle=(
            f"{split['avg_minutes_per_weekday']} min/day avg on weekdays vs "
            f"{split['avg_minutes_per_weekend_day']} min/day avg on weekends"
        ),
    ))

    cards.append(_list_card(
        "seasonality_per_artist", "time_and_rhythm", "Artist Seasons",
        [{"artist": a["artist"], "peak_season": a["peak_season"]} for a in t["seasonality_per_artist"]],
    ))

    streak = t["longest_streak"]
    cards.append(_stat_card(
        "longest_streak", "time_and_rhythm", "Longest Listening Streak",
        streak["streak_days"],
        subtitle=f"{streak['start_date']} to {streak['end_date']}" if streak["streak_days"] else None,
    ))

    hiatus = t["longest_hiatus"]
    if hiatus["hiatus_days"]:
        cards.append(_stat_card(
            "longest_hiatus", "time_and_rhythm", "Longest Hiatus",
            f"{hiatus['hiatus_days']} days",
            subtitle=f"Came back with \"{hiatus['comeback_track']}\" by {hiatus['comeback_artist']}",
        ))

    return cards


def _loyalty_cards(insights: dict) -> list:
    l = insights["loyalty_and_commitment"]
    cards = []

    cards.append(_list_card(
        "comeback_artists", "loyalty_and_commitment", "Comeback Artists",
        l["comeback_artists"][:10],
        subtitle="Artists you left for 3+ months and came back to",
    ))

    cards.append(_list_card(
        "time_to_10th_play", "loyalty_and_commitment", "Slow Burns vs Love at First Listen",
        l["time_to_10th_play"][:10],
    ))

    cards.append(_list_card(
        "retention_curve", "loyalty_and_commitment", "Artist Retention",
        [{"bucket": k, "count": v} for k, v in l["retention_curve"].items()],
        subtitle="How many artists you tried once vs became obsessed with",
    ))

    return cards


def _behavioral_cards(insights: dict) -> list:
    b = insights["behavioral_signals"]
    cards = []

    skipped = b["most_skipped_track"]
    if skipped.get("track"):
        cards.append(_stat_card(
            "most_skipped_track", "behavioral_signals", "Most Skipped Track",
            skipped["track"],
            subtitle=f"By {skipped['artist']} — skipped {skipped['skip_count']} times",
        ))

    on_repeat = b["on_repeat"]
    if on_repeat.get("track"):
        cards.append(_stat_card(
            "on_repeat", "behavioral_signals", "On Repeat",
            on_repeat["track"],
            subtitle=f"Played {on_repeat['repeat_count']} times in a row",
        ))

    shuffle = b["shuffle_vs_deliberate"]
    if shuffle.get("overall_shuffle_pct") is not None:
        cards.append(_stat_card(
            "shuffle_vs_deliberate", "behavioral_signals", "Shuffle vs Deliberate",
            f"{shuffle['overall_shuffle_pct']}% shuffle",
        ))

    cards.append(_stat_card(
        "completion_rate", "behavioral_signals", "Average Completion Rate",
        f"{b['completion_rate']['average_completion_rate'] * 100:.0f}%",
        subtitle="How much of each track you typically listen to",
    ))

    return cards


def _statistical_cards(insights: dict) -> list:
    s = insights["statistical_framing"]
    cards = []

    cards.append(_stat_card(
        "total_listening_time", "statistical_framing", "Total Listening Time",
        f"{s['total_listening_time']['total_hours']} hours",
        subtitle=f"That's {s['total_listening_time']['total_days']} days",
    ))

    cards.append(_stat_card(
        "gini_concentration", "statistical_framing", "Listening Concentration",
        s["gini_concentration"]["gini"],
        subtitle="0 = evenly spread across artists, 1 = all one artist",
    ))

    session = s["average_session_length"]
    cards.append(_stat_card(
        "average_session_length", "statistical_framing", "Average Session",
        f"{session['average_session_minutes']} min",
        subtitle=f"~{session['average_tracks_per_session']} tracks per session, across {session['total_sessions']} sessions",
    ))

    return cards


def build_shareable_cards(cleaned_df: pd.DataFrame) -> dict:
    """
    Full pipeline: build every shareable card from a cleaned, localized
    streaming history DataFrame.

    Args:
        cleaned_df: output of clean.clean_streaming_history().

    Returns:
        The full story-JSON dict: {generated_at, disclaimer, shareable_cards}.
    """
    real_plays = filter_real_plays(cleaned_df)
    insights = build_insights(cleaned_df)

    cards = []
    cards += _baseline_cards(cleaned_df, real_plays)
    cards += _time_and_rhythm_cards(insights)
    cards += _loyalty_cards(insights)
    cards += _behavioral_cards(insights)
    cards += _statistical_cards(insights)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": DISCLAIMER,
        "shareable_cards": cards,
    }


if __name__ == "__main__":
    import json
    from pathlib import Path
    from loader import load_streaming_history
    from clean import clean_streaming_history

    project_root = Path(__file__).resolve().parents[2]  # backend/
    data_folder = project_root / "data" / "raw"

    raw = load_streaming_history(str(data_folder))
    cleaned = clean_streaming_history(raw, user_timezone="America/New_York")
    story = build_shareable_cards(cleaned)

    output_path = project_root / "data" / "story.json"
    with open(output_path, "w") as f:
        json.dump(story, f, indent=2)

    print(f"\nSaved story JSON to {output_path}")
    print(f"Total cards: {len(story['shareable_cards'])}")
    for card in story["shareable_cards"]:
        print(f"  [{card['category']}] {card['id']} ({card['type']})")