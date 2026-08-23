"""
database.py

Sets up the SQLModel engine and session for the app's single table:
stored analysis results, keyed by UUID.

Reads DATABASE_URL from the environment (via a local .env file when
running locally, or Render's environment variables in production —
same variable name, no code difference between environments).
"""

import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, Session, create_engine

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Add it to a .env file locally, or to Render's environment variables in production."
    )

# Neon requires SSL. If the connection string doesn't already specify
# it, add it rather than failing at connect time with an unclear error.
if "sslmode" not in DATABASE_URL:
    separator = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    """Create tables that don't exist yet. Safe to call on every startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a DB session, closed automatically after the request."""
    with Session(engine) as session:
        yield session