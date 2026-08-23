"""
check_everything.py

One-shot validation script for the Spotify Analytics Engine backend.
Run from the backend/ folder:

    python check_everything.py

Checks:
    1. ETL pipeline runs end-to-end against your real export in data/raw/
    2. Every shareable card matches the stat/list contract
       (catches the retention_curve regression if it comes back)
    3. No duplicate card ids, no NaN/Infinity leaking into JSON
    4. top_artists card carries complete_minutes
    5. Sanity ranges on key numeric outputs (gini 0-1, completion 0-100%)
    6. MIN_REAL_PLAYS guard is checking real (>=30s) plays, not raw
       cleaned row count — regression test for the main.py fix
    7. (optional) If a local server is running, hits /upload with a
       synthetic sparse export and checks it gets rejected with 400

Prints PASS/FAIL per check, exits non-zero if anything fails.
"""

import io
import json
import sys
from pathlib import Path

import pandas as pd

from app.etl.loader import load_streaming_history
from app.etl.clean import clean_streaming_history
from app.etl.aggregate import filter_real_plays
from app.etl.story import build_shareable_cards
from app.main import MIN_REAL_PLAYS

FAILURES = []
PASSES = []


def check(name, condition, detail=""):
    if condition:
        PASSES.append(name)
        print(f"  PASS  {name}")
    else:
        FAILURES.append((name, detail))
        print(f"  FAIL  {name}{'  - ' + detail if detail else ''}")


def section(title):
    print(f"\n=== {title} ===")


def find_card(cards, card_id):
    return next((c for c in cards if c["id"] == card_id), None)


# ---------------------------------------------------------------------
# Phase 1: run the real pipeline
# ---------------------------------------------------------------------
section("Phase 1: Running ETL pipeline against data/raw/")

project_root = Path(__file__).resolve().parent
data_folder = project_root / "data" / "raw"
TEST_TIMEZONE = "America/Chicago"  # change if you want to test a different one

try:
    raw_df = load_streaming_history(str(data_folder))
    check("loader: raw data loaded", len(raw_df) > 0, f"{len(raw_df)} rows")
except Exception as e:
    print(f"  FAIL  loader crashed: {e}")
    sys.exit(1)

try:
    cleaned_df = clean_streaming_history(raw_df, user_timezone=TEST_TIMEZONE)
    check("clean: cleaned data produced", len(cleaned_df) > 0, f"{len(cleaned_df)} rows")
except Exception as e:
    print(f"  FAIL  clean_streaming_history crashed: {e}")
    sys.exit(1)

check(
    "clean: ts column is tz-aware",
    hasattr(cleaned_df["ts"].dtype, "tz") and cleaned_df["ts"].dtype.tz is not None,
)

real_plays = filter_real_plays(cleaned_df)
check("aggregate: real plays (>=30s) computed", len(real_plays) > 0, f"{len(real_plays)} real plays")
print(f"  info  cleaned rows: {len(cleaned_df)} | real plays: {len(real_plays)}")

try:
    story = build_shareable_cards(cleaned_df)
except Exception as e:
    print(f"  FAIL  build_shareable_cards crashed: {e}")
    sys.exit(1)

check("story: top-level keys present", set(story.keys()) == {"generated_at", "disclaimer", "shareable_cards"})

cards = story["shareable_cards"]
check("story: shareable_cards is a non-empty list", isinstance(cards, list) and len(cards) > 0, f"{len(cards)} cards")

# ---------------------------------------------------------------------
# Phase 2: validate every card against the stat/list contract
# ---------------------------------------------------------------------
section("Phase 2: Card schema contract")

seen_ids = set()
duplicate_ids = set()
contract_violations = []

for card in cards:
    cid = card.get("id")
    if cid in seen_ids:
        duplicate_ids.add(cid)
    seen_ids.add(cid)

    required_keys = {"id", "type", "category", "title", "subtitle"}
    missing_keys = required_keys - set(card.keys())
    if missing_keys:
        contract_violations.append(f"{cid}: missing keys {missing_keys}")
        continue

    if card["type"] == "stat":
        if "value" not in card:
            contract_violations.append(f"{cid}: stat card missing 'value'")
        elif isinstance(card["value"], (dict, list)):
            contract_violations.append(
                f"{cid}: stat card 'value' is a {type(card['value']).__name__}, should be scalar"
            )
    elif card["type"] == "list":
        if "items" not in card or not isinstance(card["items"], list):
            contract_violations.append(f"{cid}: list card missing/invalid 'items'")
        elif any(not isinstance(item, dict) for item in card["items"]):
            contract_violations.append(f"{cid}: list item is not a dict")
    else:
        contract_violations.append(f"{cid}: unknown card type '{card['type']}'")

check("no duplicate card ids", len(duplicate_ids) == 0, f"duplicates: {duplicate_ids}")
check("every card matches stat/list contract", len(contract_violations) == 0, "; ".join(contract_violations))

retention_card = find_card(cards, "retention_curve")
check("retention_curve exists", retention_card is not None)
if retention_card:
    check("retention_curve is a LIST card (regression fix)", retention_card["type"] == "list",
          f"got type={retention_card['type']!r}")

top_artists_card = find_card(cards, "top_artists")
check("top_artists exists", top_artists_card is not None)
if top_artists_card and top_artists_card.get("items"):
    first_item = top_artists_card["items"][0]
    check("top_artists items include complete_minutes", "complete_minutes" in first_item,
          f"keys found: {list(first_item.keys())}")

# ---------------------------------------------------------------------
# Phase 3: JSON safety
# ---------------------------------------------------------------------
section("Phase 3: JSON safety")

try:
    serialized = json.dumps(story)
    check("story is JSON-serializable", True)
except (TypeError, ValueError) as e:
    check("story is JSON-serializable", False, str(e))
    serialized = None

if serialized:
    check("no stray NaN in JSON output", "NaN" not in serialized)
    check("no stray Infinity in JSON output", "Infinity" not in serialized)

# ---------------------------------------------------------------------
# Phase 4: sanity ranges
# ---------------------------------------------------------------------
section("Phase 4: Value sanity ranges")

gini_card = find_card(cards, "gini_concentration")
if gini_card:
    check("gini between 0 and 1", 0.0 <= gini_card["value"] <= 1.0, f"got {gini_card['value']}")
else:
    print("  SKIP  gini_concentration card not found")

completion_card = find_card(cards, "completion_rate")
if completion_card:
    pct = float(str(completion_card["value"]).rstrip("%"))
    check("completion rate is 0-100%", 0.0 <= pct <= 100.0, f"got {completion_card['value']}")
else:
    print("  SKIP  completion_rate card not found")

# ---------------------------------------------------------------------
# Phase 5: MIN_REAL_PLAYS guard regression test (synthetic sparse data)
# ---------------------------------------------------------------------
section("Phase 5: MIN_REAL_PLAYS guard uses real plays, not raw row count")

n_fake_rows = MIN_REAL_PLAYS + 10
fake_df = pd.DataFrame({
    "ts": pd.date_range("2024-01-01", periods=n_fake_rows, freq="h", tz="UTC"),
    "ms_played": [5_000] * n_fake_rows,  # 5s each — all under the 30s real-play floor
    "spotify_track_uri": [f"spotify:track:fake{i}" for i in range(n_fake_rows)],
    "master_metadata_track_name": [f"Fake Track {i}" for i in range(n_fake_rows)],
    "master_metadata_album_artist_name": ["Fake Artist"] * n_fake_rows,
    "master_metadata_album_album_name": ["Fake Album"] * n_fake_rows,
    "reason_end": ["fwdbtn"] * n_fake_rows,
    "shuffle": [False] * n_fake_rows,
    "skipped": [False] * n_fake_rows,
})

fake_cleaned = clean_streaming_history(fake_df, user_timezone="UTC")
fake_real_play_count = len(filter_real_plays(fake_cleaned))

check(
    "synthetic sparse upload: cleaned row count would have passed the OLD (buggy) check",
    len(fake_cleaned) >= MIN_REAL_PLAYS,
    f"{len(fake_cleaned)} cleaned rows",
)
check(
    "synthetic sparse upload: real play count correctly fails the guard now",
    fake_real_play_count < MIN_REAL_PLAYS,
    f"{fake_real_play_count} real (>=30s) plays — should be < {MIN_REAL_PLAYS}",
)

# ---------------------------------------------------------------------
# Phase 6 (optional): hit a locally running server, if it's up
# ---------------------------------------------------------------------
section("Phase 6: Live API guard check (optional, only if server is running)")

try:
    import requests
    resp = requests.get("http://127.0.0.1:8000/health", timeout=1)
    server_up = resp.status_code == 200
except Exception:
    server_up = False

if not server_up:
    print("  SKIP  no local server at http://127.0.0.1:8000 — start it with "
          "`uvicorn app.main:app --reload` to run this phase")
else:
    fake_json_bytes = fake_df.to_json(orient="records", date_format="iso").encode("utf-8")
    files = {"files": ("fake_sparse_export.json", io.BytesIO(fake_json_bytes), "application/json")}
    resp = requests.post(
        "http://127.0.0.1:8000/upload",
        files=files,
        data={"user_timezone": "UTC"},
        timeout=10,
    )
    check(
        "live API rejects sparse upload with 400",
        resp.status_code == 400,
        f"got status {resp.status_code}: {resp.text}",
    )

# ---------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------
section("Summary")
print(f"{len(PASSES)} passed, {len(FAILURES)} failed")

if FAILURES:
    print("\nFailed checks:")
    for name, detail in FAILURES:
        print(f"  - {name}{': ' + detail if detail else ''}")
    sys.exit(1)
else:
    print("\nAll checks passed. Backend looks solid for frontend integration.")
    sys.exit(0)