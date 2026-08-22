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

def listening_by_period_of_day(df):
    plays = df[df["is_play"]].copy()

    def get_period(hour):
        if hour < 6:
            return "Night"
        elif hour < 12:
            return "Morning"
        elif hour < 18:
            return "Afternoon"
        else:
            return "Evening"

    plays["period_of_day"] = plays["hour"].apply(get_period)

    return (
        plays.groupby("period_of_day")["minutes_played"]
        .sum()
        .reindex(["Night", "Morning", "Afternoon", "Evening"])
    )

def top_artist_by_year(df):
    plays = df[
        df["is_play"] &
        df["master_metadata_album_artist_name"].notna()
    ]

    artist_year = (
        plays.groupby(
            ["year", "master_metadata_album_artist_name"]
        )["minutes_played"]
        .sum()
        .reset_index()
    )

    return (
        artist_year.loc[
            artist_year.groupby("year")["minutes_played"].idxmax()
        ]
        .sort_values("year")
        .set_index("year")
    )

def top_track_by_year(df):
    plays = df[
        df["is_play"] &
        df["master_metadata_track_name"].notna()
    ]

    track_year = (
        plays.groupby(
            ["year", "master_metadata_track_name"]
        )["minutes_played"]
        .sum()
        .reset_index()
    )

    return (
        track_year.loc[
            track_year.groupby("year")["minutes_played"].idxmax()
        ]
        .sort_values("year")
        .set_index("year")
    )

def longest_listening_gap(df):
    plays = df.loc[df["is_play"]].copy()

    listening_dates = sorted(plays["date"].unique())

    if len(listening_dates) < 2:
        return None

    gaps = []

    for i in range(1, len(listening_dates)):
        previous_date = listening_dates[i - 1]
        current_date = listening_dates[i]

        gap_days = (current_date - previous_date).days

        gaps.append({
            "last_listening_date": previous_date,
            "first_listening_date": current_date,
            "gap_days": gap_days,
        })

    longest_gap = max(gaps, key=lambda x: x["gap_days"])

    return_track = (
    plays.loc[plays["date"] == longest_gap["first_listening_date"]]
    .sort_values("ts")
    .iloc[0]
)

    longest_gap["return_track"] = return_track["master_metadata_track_name"]
    longest_gap["return_artist"] = return_track["master_metadata_album_artist_name"]

    return longest_gap