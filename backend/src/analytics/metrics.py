def total_minutes_played(df):
    return df["minutes_played"].sum()

def unique_tracks(df):
    return df["master_metadata_track_name"].nunique()