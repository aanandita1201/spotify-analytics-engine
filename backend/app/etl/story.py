"""
story.py

Takes the list of artist profile dicts from aggregate.py and shapes
them into the final "story JSON" — the pure-data contract the frontend
will consume to build the Discovery Journey scrollytelling experience.

No visual-mapping fields (size, color, position) live here by design —
that's frontend-layer logic, decided once we're actually building the
scroll experience and can judge what looks good on screen.

Field naming note: we use "first_streamed_date" rather than
"discovery_date", and "obsession_period_start" rather than
"became_fan_date", because the data can only ever reflect Spotify
streaming behavior — not when someone actually first heard an artist
or how they felt about them. This keeps the data model itself honest,
independent of whatever wording the frontend eventually uses.
"""

from datetime import datetime
import pandas as pd


def _serialize_timestamp(ts):
    """Convert a pandas Timestamp (or None) to an ISO date string (or None)."""
    if ts is None or pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def build_artist_story(profile: dict) -> dict:
    """
    Convert one artist profile dict (from aggregate.build_artist_profile)
    into its story-JSON shape.

    Args:
        profile: dict as returned by aggregate.build_artist_profile().

    Returns:
        A dict matching the story-JSON schema for one artist.
    """
    return {
        "artist": profile["artist"],
        "total_ms_played": profile["total_ms_played"],
        "total_hours_played": round(profile["total_ms_played"] / 1000 / 60 / 60, 1),
        "first_streamed_date": _serialize_timestamp(profile["discovery_date"]),
        "entry_point_song": profile["entry_point_song"],
        "obsession_period_start": _serialize_timestamp(profile["became_fan_date"]),
        "most_played_song": profile["most_played_song"],
        "top_10_songs": profile["top_10_songs"],
        "favorite_album": profile["favorite_album"],
    }


def build_story_json(profiles: list) -> dict:
    """
    Build the full Discovery Journey story-JSON from all artist profiles.

    Args:
        profiles: list of profile dicts, as returned by
                  aggregate.build_discovery_journey().

    Returns:
        The full story-JSON dict, ready to be saved or returned by an API.
    """
    return {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": (
            "These stats reflect your Spotify streaming history only — "
            "not necessarily when you first heard an artist or how you "
            "felt about them in real life."
        ),
        "artists": [build_artist_story(p) for p in profiles],
    }


if __name__ == "__main__":
    import json
    from pathlib import Path
    from loader import load_streaming_history
    from clean import clean_streaming_history
    from aggregate import build_discovery_journey

    project_root = Path(__file__).resolve().parents[2]  # backend/
    data_folder = project_root / "data" / "raw"

    raw = load_streaming_history(str(data_folder))
    cleaned = clean_streaming_history(raw)
    profiles = build_discovery_journey(cleaned)
    story = build_story_json(profiles)

    # Save it so you can inspect the actual output file, and so the
    # frontend has something real to point at once that phase starts
    output_path = project_root / "data" / "story.json"
    with open(output_path, "w") as f:
        json.dump(story, f, indent=2)

    print(f"\nSaved story JSON to {output_path}")
    print(f"Artists included: {[a['artist'] for a in story['artists']]}")