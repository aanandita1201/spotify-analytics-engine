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

def listening_streaks(df):
    listening_dates = (
        df.loc[df["is_play"], "date"]
        .drop_duplicates()
        .sort_values()
    )

    if listening_dates.empty:
        return {
            "longest_streak": 0,
            "current_streak": 0,
        }

    date_diffs = listening_dates.diff().dt.days

    streak_id = (date_diffs != 1).cumsum()

    streak_lengths = listening_dates.groupby(streak_id).size()

    longest_streak = int(streak_lengths.max())

    current_streak = int(streak_lengths.iloc[-1])

    return {
        "longest_streak": longest_streak,
        "current_streak": current_streak,
    }

def repeat_rate(df):
    plays = (
        df.loc[df["is_play"] & df["master_metadata_track_name"].notna()]
        .sort_values("ts")
        .copy()
    )

    if plays.empty:
        return 0.0

    plays["is_repeat"] = plays["master_metadata_track_name"].duplicated()

    return plays["is_repeat"].mean()

def artist_diversity(df):
    plays = df[
        df["is_play"] &
        df["master_metadata_album_artist_name"].notna()
    ]

    if plays.empty:
        return 0.0

    artist_counts = (
        plays["master_metadata_album_artist_name"]
        .value_counts()
    )

    top_10_plays = artist_counts.head(10).sum()

    return top_10_plays / len(plays)