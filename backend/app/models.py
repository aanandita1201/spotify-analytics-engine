"""
models.py

Single table: one row per completed analysis, keyed by UUID.

Only the final aggregated story JSON is stored here. Per the privacy
architecture, the raw uploaded file and any PII-adjacent fields never
reach this table — they're stripped in clean.py and discarded once
build_shareable_cards() returns, before this row is ever created.
"""

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class AnalysisResult(SQLModel, table=True):
    __tablename__ = "analysis_results"

    id: uuid_lib.UUID = Field(default_factory=uuid_lib.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_timezone: str = Field(default="UTC")

    # The full { generated_at, disclaimer, shareable_cards } dict from
    # story.build_shareable_cards(). Plain JSON (not JSONB) for now
    # since we're not querying inside it — just fetching whole rows by id.
    story: Dict[str, Any] = Field(sa_column=Column(JSON))