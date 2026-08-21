import pandas as pd


def clean_streaming_history(records):
    df = pd.DataFrame(records)

    if df.empty:
        return df

    # Keep only music listening records
    df = df.dropna(
        subset=[
            "ts",
            "ms_played",
            "master_metadata_track_name",
            "master_metadata_album_artist_name",
        ]
    )

    # Convert data types
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    df["ms_played"] = pd.to_numeric(df["ms_played"], errors="coerce")

    # Remove records with invalid values
    df = df.dropna(subset=["ts", "ms_played"])

    return df