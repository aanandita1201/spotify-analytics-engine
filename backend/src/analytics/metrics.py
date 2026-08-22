def total_minutes_played(df):
    return df.loc[df["is_play"], "minutes_played"].sum()

def unique_tracks(df):
    return df.loc[df["is_play"], "master_metadata_track_name"].nunique()

def unique_artists(df):
    return df.loc[df["is_play"], "master_metadata_album_artist_name"].nunique()

def top_artists(df, limit=10):
    return (
        df.loc[df["is_play"]]
        .groupby("master_metadata_album_artist_name")["minutes_played"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )

def top_tracks(df, limit=10):
    return (
        df.loc[df["is_play"]]
        .groupby("master_metadata_track_name")["minutes_played"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )

def total_plays(df):
    return df["is_play"].sum()

def listening_by_year(df):
    return (
        df.loc[df["is_play"]]
        .groupby("year")["minutes_played"]
        .sum()
        .sort_index()
    )

def listening_by_month(df):
    return (
        df.loc[df["is_play"]]
        .groupby(["year", "month"])["minutes_played"]
        .sum()
        .sort_index()
    )

def listening_by_day_of_week(df):
    return (
        df.loc[df["is_play"]]
        .groupby("day_of_week")["minutes_played"]
        .sum()
    )

def listening_by_hour(df):
    return (
        df.loc[df["is_play"]]
        .groupby("hour")["minutes_played"]
        .sum()
        .sort_index()
    )

def listening_by_date(df):
    return (
        df.loc[df["is_play"]]
        .groupby("date")["minutes_played"]
        .sum()
        .sort_values(ascending=False)
    )