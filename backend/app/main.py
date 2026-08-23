"""
main.py

The Spotify Analytics Engine API. Two endpoints:

    POST /upload    — accepts one or more Extended Streaming History
                       JSON files + an optional timezone, runs the full
                       ETL/insights pipeline in memory, stores only the
                       final aggregated result, returns its UUID.

    GET /results/{id} — fetches a previously computed result by UUID.

Privacy note: uploaded file content and the intermediate DataFrames
(raw_df, cleaned_df) exist only for the duration of the request and
are never written to disk. Only `story` — the final aggregated,
non-identifying shareable_cards dict — gets persisted.
"""

import uuid as uuid_lib
from typing import List

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .database import get_session, init_db
from .models import AnalysisResult

from .etl.loader import load_streaming_history_from_bytes
from .etl.clean import clean_streaming_history
from .etl.story import build_shareable_cards
from .etl.aggregate import filter_real_plays

app = FastAPI(title="Spotify Analytics Engine")

# Wide open for now since the frontend isn't deployed yet. Tighten this
# to the actual Vercel domain once the frontend phase starts.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Columns that must be present for this to plausibly be a real Spotify
# Extended Streaming History export, checked before we spend time
# running the full pipeline on garbage input.
REQUIRED_COLUMNS = {
    "ts",
    "ms_played",
    "spotify_track_uri",
    "master_metadata_track_name",
    "master_metadata_album_artist_name",
}

# Below this many real (post-clean) plays, most of the locked metrics
# (comeback artists, seasonality, retention curve) are too sparse to
# mean anything, so we reject early with a clear message instead of
# returning a story full of nulls.
MIN_REAL_PLAYS = 50


@app.on_event("startup")
def on_startup():
    init_db()


def _read_uploads(files: List[UploadFile]) -> pd.DataFrame:
    """Read uploaded files into memory and hand off to the loader. No disk I/O."""
    file_contents = [(f.filename, f.file.read()) for f in files]

    try:
        return load_streaming_history_from_bytes(file_contents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _validate_schema(df: pd.DataFrame):
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "These don't look like Spotify Extended Streaming History files. "
                f"Missing expected columns: {sorted(missing)}"
            ),
        )


@app.post("/upload")
async def upload_streaming_history(
    files: List[UploadFile] = File(...),
    user_timezone: str = Form(default="UTC"),
    session: Session = Depends(get_session),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    raw_df = _read_uploads(files)
    _validate_schema(raw_df)

    cleaned_df = clean_streaming_history(raw_df, user_timezone=user_timezone)

    real_play_count = len(filter_real_plays(cleaned_df))
    if real_play_count < MIN_REAL_PLAYS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough listening data to generate meaningful stats "
                f"(found {real_play_count} plays of 30s or longer, "
                f"need at least {MIN_REAL_PLAYS})."
            ),
        )

    story = build_shareable_cards(cleaned_df)

    result = AnalysisResult(user_timezone=user_timezone, story=story)
    session.add(result)
    session.commit()
    session.refresh(result)

    # raw_df and cleaned_df go out of scope here and are garbage
    # collected — nothing from them exists beyond this function call.
    return {"id": str(result.id)}


@app.get("/results/{result_id}")
def get_results(result_id: str, session: Session = Depends(get_session)):
    try:
        parsed_id = uuid_lib.UUID(result_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = session.get(AnalysisResult, parsed_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    return {
        "id": str(result.id),
        "created_at": result.created_at.isoformat(),
        **result.story,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}