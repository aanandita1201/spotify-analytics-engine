def total_minutes_played(df):
    return df["minutes_played"].sum()

def unique_tracks(df):
    return df["master_metadata_track_name"].nunique()

def unique_artists(df):
    return df["master_metadata_album_artist_name"].nunique()

def top_artists(df, limit=10):
    return (
        df.groupby("master_metadata_album_artist_name")["minutes_played"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )